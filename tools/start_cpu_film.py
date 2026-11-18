"""Build/start the local film profile, using CPU models only and no GPU lifecycle calls."""
import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = ROOT / 'integrations/toonflow'
PIN = '6086cdffceb704a632eca143dd16cd461a78cdac'
LOCAL_PROMPT = '''You are the local film assistant. Reply in the user's language, briefly and accurately.
Use filmProject as the source of truth for scripts, project revisions, CPU work, takes and review state.
For production requests read the workflow skill with skillOperator first; for a status question call filmProject directly.
Use stable creationId/commandId values and expectedRevision from get. Retry an uncertain request with the identical id and payload.
Human storyboard, take, retry and final-film decisions happen at the local review URL. Never claim or record approval on the owner's behalf.
All production inference stays local. GPU execution is disabled: do not call GPU services, free memory, stop other services, install media providers or use hosted inference.
Prepare voices and animatics on CPU. render-ready saves requests only. When waiting for review or GPU work, report the stage and review link, then stop.
Closing chat/canvas does not cancel production. Cancel only when explicitly requested. Do not delegate a simple film task.
{{tools}}
{{guidelines}}
Environment: {{environment}}'''


def bun_executable():
    found = shutil.which('bun') or Path(os.environ['USERPROFILE']) / '.bun/bin/bun.exe'
    if not Path(found).is_file():
        raise RuntimeError('Bun is missing; install the pinned Toonflow dependencies first')
    return str(found)


def setup(vendor, profile, model_port, film_root=ROOT / 'film-projects'):
    if (profile / 'settings.json').exists() and not (profile / 'build-provenance.json').is_file():
        raise RuntimeError('Use a new dedicated film profile; refusing to alter an unrelated settings file')
    current = subprocess.run(['git', '-c', 'safe.directory=' + vendor.as_posix(), '-C', str(vendor), 'rev-parse', 'HEAD'],
                             capture_output=True, text=True, check=True).stdout.strip()
    if current != PIN:
        raise RuntimeError(f'Toonflow revision must be {PIN}; found {current}. Do not update it implicitly.')
    if not (vendor / 'build/web/index.html').is_file():
        raise RuntimeError('Build the pinned Toonflow checkout first: bun run build')
    modules = INTEGRATION / 'node_modules'; modules.mkdir(parents=True, exist_ok=True)
    sources = {
        '@toonflow/nodes-scaffold': vendor / 'packages/nodeScaffold',
        '@toonflow/tools-scaffold': vendor / 'packages/toolScaffold',
        'vue': vendor / 'packages/nodeScaffold/node_modules/vue',
        '@vue-flow/core': vendor / 'packages/nodeScaffold/node_modules/@vue-flow/core',
        'element-plus': vendor / 'packages/nodeScaffold/node_modules/element-plus',
        'zod': vendor / 'packages/nodeScaffold/node_modules/zod',
        'vite': vendor / 'packages/nodeScaffold/node_modules/vite',
        'typescript': vendor / 'packages/nodeScaffold/node_modules/typescript',
        'vue-tsc': vendor / 'packages/nodeScaffold/node_modules/vue-tsc',
        '@types/bun': vendor / 'node_modules/@types/bun',
    }
    for name, source in sources.items():
        if not source.is_dir():
            raise RuntimeError(f'Installed SDK dependency missing: {source}')
        link = modules / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.exists():
            if link.resolve() != source.resolve():
                raise RuntimeError(f'Refusing to replace an unrelated dependency at {link}')
            continue
        if os.name == 'nt':
            # A directory junction needs no developer-mode symlink privilege.
            quote = lambda p: "'" + str(p).replace("'", "''") + "'"
            subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                            'New-Item -ItemType Junction -Path ' + quote(link) + ' -Target ' + quote(source.resolve()) + ' | Out-Null'], check=True)
        else:
            link.symlink_to(source.resolve(), target_is_directory=True)
    bun = bun_executable()
    env = os.environ.copy(); env.update(NODE_ENV='production', CUDA_VISIBLE_DEVICES='-1')
    subprocess.run([bun, 'run', 'filmProjectService/build.ts'], cwd=INTEGRATION, env=env, check=True)
    vite = sources['vite'] / 'bin/vite.js'
    subprocess.run([bun, str(vite.resolve()), 'build', '--config', 'filmProject/vite.config.ts'],
                   cwd=INTEGRATION, env=env, check=True)
    vue_tsc = sources['vue-tsc'] / 'bin/vue-tsc.js'
    subprocess.run([bun, str(vue_tsc.resolve()), '-p', 'tsconfig.json', '--noEmit'], cwd=INTEGRATION, env=env, check=True)
    profile.mkdir(parents=True, exist_ok=True)
    tools = profile / 'bundledTools'; tools.mkdir(exist_ok=True)
    for name in ('canvas', 'askUser', 'skillOperator'):
        shutil.copyfile(vendor / f'build/tools/{name}.tool.js', tools / f'{name}.tool.js')
    (tools / 'workspace.tool.js').unlink(missing_ok=True)
    shutil.copyfile(INTEGRATION / 'build/tools/filmProject.tool.js', tools / 'filmProject.tool.js')
    settings = profile / 'settings.json'
    provenance = profile / 'build-provenance.json'
    prior = json.loads(provenance.read_text(encoding='utf8')) if provenance.exists() else {}
    if settings.exists() and not prior:
        raise RuntimeError('Use a new dedicated film profile; refusing to alter an unrelated settings file')
    if not settings.exists():
        settings.write_text(json.dumps({'settings': {'customProviders': [{'id': 'localCpu', 'label': 'Local CPU',
            'apiUrl': f'http://127.0.0.1:{model_port}/v1', 'apiKey': 'local-placeholder', 'protocol': 'openai-completions',
            'models': [{'id': 'local-qwen', 'label': 'Qwen 3.5 4B CPU', 'contextWindow': 16384,
                        'maxOutputTokens': 2400, 'reasoningEfforts': False}]}]}, 'mediaGenerationDisabledOnce': True}, indent=2), encoding='utf8')
    config = json.loads(settings.read_text(encoding='utf8'))
    config.setdefault('settings', {}).setdefault('agentSystemPrompt', LOCAL_PROMPT)
    if prior.get('profile_schema_version', 1) < 2:
        for provider in config['settings'].get('customProviders', []):
            if provider.get('id') == 'localCpu':
                for model in provider.get('models', []):
                    if model.get('id') == 'local-qwen' and model.get('contextWindow') == 8192:
                        model['contextWindow'] = 16384
        installed = profile / 'tools'; installed.mkdir(exist_ok=True)
        (installed / 'workspace.disabled').touch()
    temporary_settings = settings.with_suffix('.next.json')
    temporary_settings.write_text(json.dumps(config, indent=2), encoding='utf8')
    os.replace(temporary_settings, settings)
    workflow = INTEGRATION / 'skills/workflow/SKILL.md'
    workflow_hash = hashlib.sha256(workflow.read_bytes()).hexdigest()
    installed_workflow = profile / 'skills/workflow/SKILL.md'
    if installed_workflow.exists():
        known_hash = hashlib.sha256(installed_workflow.read_bytes()).hexdigest()
        if known_hash != workflow_hash:
            if known_hash != prior.get('workflow_sha256'):
                raise RuntimeError('Installed workflow was edited; merge it manually before updating this profile')
            shutil.copyfile(workflow, installed_workflow)
    (profile / 'workspaces/films').mkdir(parents=True, exist_ok=True)
    canvas_path = profile / 'workspaces/films/filmProject.json'
    if not canvas_path.exists():
        acceptance = Path(film_root) / 'cpuAcceptance.json'
        project_id = json.loads(acceptance.read_text(encoding='utf8'))['project_id'] if acceptance.is_file() else ''
        canvas = {'toonflowCanvas': True, 'nodes': [{'id': 'localFilmProject', 'type': 'remote-filmProject',
            'initialized': False, 'position': {'x': 40, 'y': 40}, 'data': {'label': 'Film Project',
            'projectId': project_id, 'outputs': {'project': {'dataType': 'STRING', 'value': project_id}}}}],
            'edges': [], 'viewport': {'x': 0, 'y': 0, 'zoom': 1}}
        canvas_path.write_text(json.dumps(canvas, indent=2), encoding='utf8')
    provenance.write_text(json.dumps({'toonflow_commit': PIN, 'profile_schema_version': 2, 'workflow_sha256': workflow_hash,
        'node': 'filmProject', 'version': '0.1.0', 'gpu_policy': 'disabled',
        'production_inference': 'local-cpu-only', 'account_required': False}, indent=2), encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--setup-only', action='store_true')
    mode.add_argument('--skip-build', action='store_true')
    parser.add_argument('--backend-only', action='store_true')
    mode.add_argument('--stop', action='store_true', help='Ask this profile\'s CPU launcher to stop its own services')
    parser.add_argument('--vendor', type=Path, default=ROOT / 'local-runtime/evaluations/toonflow')
    parser.add_argument('--profile', type=Path, default=ROOT / 'local-runtime/film-toonflow')
    parser.add_argument('--root', type=Path, default=ROOT / 'film-projects')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--toonflow-port', type=int, default=33030)
    parser.add_argument('--model-port', type=int, default=33031)
    args = parser.parse_args()
    if args.backend_only and args.setup_only:
        parser.error('--setup-only builds the Toonflow profile; omit --backend-only')
    vendor, profile = args.vendor.resolve(), args.profile.resolve()
    if args.stop:
        session = json.loads((profile / 'session.json').read_text(encoding='utf8'))
        if session.get('active'):
            (profile / 'stop-request.json').write_text(json.dumps({'session_id': session['session_id']}), encoding='utf8')
        print('CPU service stop requested for this profile.'); return
    if not args.backend_only:
        current = subprocess.run(['git', '-c', 'safe.directory=' + vendor.as_posix(), '-C', str(vendor), 'rev-parse', 'HEAD'],
                                 capture_output=True, text=True, check=True).stdout.strip()
        if current != PIN:
            parser.error('Toonflow checkout differs from the pinned release; rebuild against the recorded revision')
    if args.port != 8766:
        parser.error('The v1 extension uses film backend port 8766')
    if not args.backend_only and not args.skip_build:
        setup(vendor, profile, args.model_port, args.root.resolve())
    if args.setup_only:
        print('CPU film extensions built and typechecked. Profile: ' + str(profile)); return
    ports = [args.port] if args.backend_only else [args.port, args.toonflow_port, args.model_port]
    if len(set(ports)) != len(ports):
        parser.error('Service ports must be distinct')
    for port in ports:
        with socket.socket() as sock:
            try:
                sock.bind(('127.0.0.1', port))
            except OSError:
                parser.error(f'Port {port} is already in use; existing services were left alone')
    profile.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES='-1', NODE_ENV='production',
               LOCAL_FILM_TOONFLOW_ROOT=str(vendor), LOCAL_FILM_TOONFLOW_PROFILE=str(profile),
               LOCAL_FILM_TOONFLOW_PORT=str(args.toonflow_port))
    session_id = uuid.uuid4().hex
    backend_stop = profile / ('backend-stop-' + session_id)
    commands = [[sys.executable, '-m', 'local_film.project_server', '--root', str(args.root), '--port', str(args.port),
                 '--toonflow-origin', f'http://127.0.0.1:{args.toonflow_port}', '--stop-file', str(backend_stop)]]
    if not args.backend_only:
        runtime = ROOT / 'local-runtime/llama'
        if any(runtime.glob('ggml-cuda*.dll')) or any(runtime.glob('ggml-vulkan*.dll')):
            raise RuntimeError('Use the CPU-only llama.cpp distribution for this launcher')
        env['GGML_BACKEND_DL_PATH'] = str(runtime)
        commands += [[str(runtime / 'llama-server.exe'), '-m', str(ROOT / 'local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf'),
                      '--host', '127.0.0.1', '--port', str(args.model_port), '--device', 'none', '-ngl', '0',
                      '--no-op-offload', '--no-kv-offload', '--fit', 'off', '-c', '16384', '-t', '6', '-tb', '6',
                      '--parallel', '1', '--no-webui', '--jinja', '--reasoning', 'off'],
                     [bun_executable(), str(INTEGRATION / 'launch.ts')]]
    processes, logs = [], []
    def stop(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for index, command in enumerate(commands):
            log = (profile / f'service-{index}.log').open('ab'); logs.append(log)
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
        session_record = {'gpu_policy': 'disabled', 'session_id': session_id, 'active': True,
            'owned_pids': [p.pid for p in processes], 'started': time.time()}
        (profile / 'session.json').write_text(json.dumps(session_record, indent=2), encoding='utf8')
        print(f'Film review: http://127.0.0.1:{args.port}/', flush=True)
        if not args.backend_only:
            print(f'Toonflow: http://127.0.0.1:{args.toonflow_port}/ — choose Local CPU; no sign-in required', flush=True)
        print('GPU services are untouched. Ctrl+C stops only these CPU services.', flush=True)
        while all(p.poll() is None for p in processes):
            stop_request = profile / 'stop-request.json'
            if stop_request.exists():
                try:
                    if json.loads(stop_request.read_text(encoding='utf8')).get('session_id') == session_id:
                        return
                except (OSError, ValueError):
                    pass
            time.sleep(0.5)
        raise RuntimeError('A CPU service stopped; inspect the profile service logs')
    except KeyboardInterrupt:
        pass
    finally:
        if processes and processes[0].poll() is None:
            backend_stop.touch()
            try:
                processes[0].wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
        for log in logs:
            log.close()
        if 'session_record' in locals():
            session_record.update(active=False, stopped=time.time(), exit_codes=[p.poll() for p in processes])
            (profile / 'session.json').write_text(json.dumps(session_record, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
