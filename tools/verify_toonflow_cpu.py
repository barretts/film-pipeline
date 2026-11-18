"""Real account-free Toonflow HTTP-agent/film-tool round trip, with owned CPU services."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-id', default='film-14ce7ba2-c038-5358-93e9-24fb786d0a27')
    args = parser.parse_args()
    profile = ROOT / 'local-runtime/film-toonflow'
    evidence = ROOT / 'film-projects/verification' / ('toonflow-' + time.strftime('%Y%m%d-%H%M%S'))
    evidence.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy(); env.update(PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='-1')
    launcher = [sys.executable, str(ROOT / 'tools/start_cpu_film.py')]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    log = (evidence / 'launcher.log').open('wb')
    process = subprocess.Popen(launcher + ['--skip-build'], cwd=ROOT, env=env, stdout=log,
        stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    summary = {'evidence_directory': str(evidence), 'gpu_policy': 'disabled'}
    print(json.dumps({'phase': 'starting_full_cpu_profile', 'evidence_directory': str(evidence)}), flush=True)
    def get(base, path):
        with opener.open(base + path, timeout=5) as response:
            return json.load(response)
    try:
        ready = False
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError('CPU launcher stopped; inspect launcher and profile service logs')
            try:
                models = get('http://127.0.0.1:33030', '/api/ai/models')
                health = get('http://127.0.0.1:33031', '/health')
                caps = get('http://127.0.0.1:8766', '/api/film/v1/capabilities')
                ready = health['status'] == 'ok' and caps['gpu_policy'] == 'disabled'
            except OSError:
                pass
            if ready:
                break
            time.sleep(1)
        if not ready:
            raise TimeoutError('CPU services startup deadline')
        current = get('http://127.0.0.1:8766', '/api/film/v1/projects/' + args.project_id)
        (evidence / 'models.json').write_text(json.dumps(models, indent=2), encoding='utf8')
        nodes = get('http://127.0.0.1:33030', '/api/nodes/get')
        (evidence / 'nodes.json').write_text(json.dumps(nodes, indent=2), encoding='utf8')
        hashes = {}
        for kind, filename in [('nodes', 'filmProject.umd.js'), ('tools', 'filmProject.tool.js')]:
            built = ROOT / 'integrations/toonflow/build' / kind / filename
            installed = profile / kind / filename
            hashes[kind] = {name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for name, path in [('built', built), ('installed', installed)]}
        summary['plugin_hashes'] = hashes
        summary['deployed_plugins_match'] = all(h['built'] == h['installed'] for h in hashes.values())
        if not summary['deployed_plugins_match']:
            raise RuntimeError('Installed plugin differs from the build; do not trust a stale-profile pass')
        print(json.dumps({'phase': 'full_agent_running', 'provider': 'localCpu', 'model': 'local-qwen'}), flush=True)
        body = {'directory': str(profile / 'workspaces/films'), 'providerId': 'localCpu', 'modelId': 'local-qwen',
                'prompt': 'Call the filmProject tool with operation list. From its result report each existing film project id, title, revision and status in English. Do not modify, create, approve, render, delegate or call any other tool.'}
        request = urllib.request.Request('http://127.0.0.1:33030/api/agent', json.dumps(body).encode(),
                                         {'Content-Type': 'application/json'})
        events, started = [], time.monotonic()
        try:
            response = opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            (evidence / 'http-error.txt').write_bytes(error.read())
            raise
        with response, (evidence / 'agent.ndjson').open('wb') as recording:
            for line in response:
                recording.write(line); recording.flush()
                if time.monotonic() - started > 600:
                    raise TimeoutError('Full CPU agent deadline')
                if not line.strip():
                    continue
                event = json.loads(line); events.append(event)
                if event.get('type') in ('tool', 'error', 'session', 'done'):
                    print(json.dumps({'event': event['type'], 'name': event.get('tool', {}).get('name'),
                        'status': event.get('tool', {}).get('status'), 'message': event.get('message')}), flush=True)
                if event.get('type') == 'done':
                    break
        texts = {}
        for event in events:
            if event.get('type') == 'text':
                key = event.get('blockId', 'text')
                texts[key] = event['content'] if 'content' in event else texts.get(key, '') + event.get('delta', '')
        answer = '\n'.join(texts.values())
        errors = [e for e in events if e.get('type') == 'error']
        tools = [e for e in events if e.get('type') == 'tool' and e.get('tool', {}).get('name') == 'filmProject']
        summary.update(seconds=round(time.monotonic()-started, 2), errors=errors, film_tool_events=len(tools),
                       answer=answer, expected_status=current['status'],
                       passed=bool(tools) and not errors and args.project_id in answer and current['status'] in answer,
                       installed_media_providers=[p.name for p in (profile / 'providers').glob('*.ts')])
    except Exception as error:
        summary.update(passed=False, error=str(error))
    finally:
        with (evidence / 'stop.log').open('wb') as output:
            subprocess.run(launcher + ['--stop'], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=15)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            summary['launcher_stop_timeout'] = True
        log.close(); summary['launcher_exit'] = process.poll()
        summary['closed_ports'] = {}
        for port in (8766, 33030, 33031):
            with socket.socket() as sock:
                sock.settimeout(1); summary['closed_ports'][str(port)] = sock.connect_ex(('127.0.0.1', port)) != 0
        (evidence / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(json.dumps(summary), flush=True)
    raise SystemExit(0 if summary.get('passed') and all(summary['closed_ports'].values()) else 1)


if __name__ == '__main__':
    main()
