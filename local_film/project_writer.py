"""Bounded, schema-constrained film drafting with the installed CPU llama.cpp."""
import concurrent.futures
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from .project_contract import ProjectError, validate_spec
from .project_media import ROOT

STRING = {'type': 'string'}
STRINGS = {'type': 'array', 'items': STRING}
STATE = {'type': 'object', 'additionalProperties': STRING}
LINE = {'type': 'object', 'properties': {'character': STRING, 'text': STRING,
        'source': {'type': 'string', 'enum': ['on_screen', 'off_screen', 'radio']},
        'at_seconds': {'type': 'number', 'minimum': 0}},
        'required': ['character', 'text', 'source', 'at_seconds'], 'additionalProperties': False}
SHOT_PROPERTIES = {'id': STRING, 'seconds': {'type': 'number', 'minimum': 1, 'maximum': 15},
                   'action': STRING, 'prompt': STRING, 'camera': STRING,
                   'visible_cast': STRINGS, 'offscreen_cast': STRINGS, 'requires': STRINGS,
                   'before': STATE, 'after': STATE, 'silence': {'type': 'boolean'},
                   'dialogue': {'type': 'array', 'items': LINE}}
SCHEMA = {'type': 'object', 'properties': {'schema_version': {'const': 1}, 'title': STRING,
          'brief': STRING, 'style': STRING, 'characters': STRINGS, 'initial_state': STATE,
          'shots': {'type': 'array', 'minItems': 3, 'maxItems': 8, 'items': {'type': 'object',
                    'properties': SHOT_PROPERTIES, 'required': list(SHOT_PROPERTIES), 'additionalProperties': False}}},
          'required': ['schema_version', 'title', 'brief', 'style', 'characters', 'initial_state', 'shots'],
          'additionalProperties': False}


def draft(project, payload, directory, cancelled):
    if cancelled():
        raise ProjectError('CPU draft cancelled', 409)
    runtime = ROOT / 'local-runtime/llama'
    exe = runtime / 'llama-server.exe'
    model = ROOT / 'local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf'
    if not exe.is_file() or not model.is_file():
        raise ProjectError('Local CPU writer executable/model is missing; no hosted fallback is configured')
    if any(runtime.glob('ggml-cuda*.dll')) or any(runtime.glob('ggml-vulkan*.dll')):
        raise ProjectError('Writer requires the CPU-only llama.cpp distribution; GPU backends were found')
    directory.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES='-1', GGML_BACKEND_DL_PATH=str(runtime))
    args = [str(exe), '-m', str(model), '--host', '127.0.0.1', '--port', str(port),
            '--device', 'none', '-ngl', '0', '--no-op-offload', '--no-kv-offload', '--fit', 'off',
            '-c', '16384', '-t', '6', '-tb', '6', '--parallel', '1', '--no-webui', '--jinja', '--reasoning', 'off']
    prompt = ('Write a self-contained 30–45 second short film with a visual hook in the first five seconds, '
              'a motivated character choice, and an ending that pays off the hook. One physical action per shot. '
              'Use only these character ids: ' + ', '.join(project['spec']['characters']) + '. '
              'Use short speakable dialogue, explicit silence for quiet shots, and distinguish radio/off-screen voices '
              'from visible speakers. At most one on_screen speaker per shot. Require an earlier shot whenever its '
              'approved end state is needed. before states must match the preceding after states for shared keys. '
              'No narration placeholders, cloud models, extra people or text overlays. Return only schema JSON.')
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': json.dumps({
        'brief': payload.get('brief', project['spec']['brief']), 'style': project['spec']['style']})}]
    initial_messages = list(messages)
    with (directory / 'writer.log').open('wb') as log:
        process = subprocess.Popen(args, cwd=runtime, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            endpoint = f'http://127.0.0.1:{port}'
            ready = False
            for _ in range(90):
                if cancelled():
                    raise ProjectError('CPU draft cancelled', 409)
                if process.poll() is not None:
                    raise ProjectError('CPU writer stopped during startup; inspect writer.log')
                try:
                    with opener.open(endpoint + '/health', timeout=1) as response:
                        ready = response.status == 200
                except OSError:
                    pass
                if ready:
                    break
                time.sleep(1)
            if not ready:
                raise ProjectError('CPU writer did not become ready within 90 seconds')
            for attempt in range(3):
                body = {'model': 'local-qwen', 'messages': messages, 'temperature': 0.2, 'max_tokens': 3400,
                        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'film_spec', 'schema': SCHEMA}}}
                def generate():
                    request = urllib.request.Request(endpoint + '/v1/chat/completions', json.dumps(body).encode(),
                                                     headers={'Content-Type': 'application/json'})
                    with opener.open(request, timeout=600) as response:
                        return json.load(response)
                future = executor.submit(generate)
                start = time.monotonic()
                while not future.done():
                    if cancelled():
                        raise ProjectError('CPU draft cancelled', 409)
                    if time.monotonic() - start > 600:
                        raise ProjectError('CPU writer request exceeded ten minutes')
                    time.sleep(0.2)
                raw = future.result()
                (directory / f'response-{attempt + 1}.json').write_text(json.dumps(raw, indent=2), encoding='utf8')
                try:
                    spec = validate_spec(json.loads(raw['choices'][0]['message']['content']))
                    if set(spec['characters']) != set(project['spec']['characters']):
                        raise ProjectError('Writer changed the registered cast')
                    if not 30 <= sum(s['seconds'] for s in spec['shots']) <= 45:
                        raise ProjectError('Short must run 30–45 seconds')
                    return spec
                except (ValueError, KeyError, TypeError, IndexError) as error:
                    try:
                        failed_text = raw['choices'][0]['message']['content'] or 'Invalid empty response'
                    except (KeyError, TypeError, IndexError):
                        failed_text = json.dumps(raw)
                    messages = initial_messages + [{'role': 'assistant', 'content': failed_text},
                        {'role': 'user', 'content': f'Correction: {error}. Return the complete valid JSON, correcting that issue.'}]
            raise ProjectError('CPU writer failed validation after two corrections; inspect saved raw responses')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
            executor.shutdown(wait=False, cancel_futures=True)
