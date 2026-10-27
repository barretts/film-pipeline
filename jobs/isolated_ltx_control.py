"""Control only the workspace-isolated Studio; never print credentials."""
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
isolated = ROOT / 'venvs' / 'isolated-studio-probe'
backend = Path(r'C:\Users\barrett\.unsloth\studio\unsloth_studio\Lib\site-packages\studio\backend')
os.environ['UNSLOTH_STUDIO_HOME'] = str(isolated / 'studio')
os.environ['UNSLOTH_HOME'] = str(isolated)
sys.path.insert(0, str(backend))
sys.path.insert(0, str(ROOT / 'tools'))
from auth import storage
import studio_mcp
from utils.mcp_access import set_mcp_enabled

studio_mcp.ENDPOINT = 'http://127.0.0.1:8894/mcp/'
set_mcp_enabled(True)
key_file = isolated / 'studio' / 'auth' / '.film_comparison_key'
if key_file.exists():
    key = key_file.read_text(encoding='utf-8').strip()
else:
    key, row = storage.create_api_key(username='unsloth', name='local-film-comparison')
    key_file.write_text(key, encoding='utf-8')
try:
    api = studio_mcp.Studio(key, timeout=120)
    if len(sys.argv) > 1 and sys.argv[1] == 'video-progress':
        request = urllib.request.Request('http://127.0.0.1:8894/api/inference/video/load-progress',
                                         headers={'Authorization': 'Bearer ' + key})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=15) as response:
            print(json.dumps(studio_mcp.safe(json.load(response), key), ensure_ascii=True))
    elif len(sys.argv) == 1 or sys.argv[1] == 'schema':
        result = api.rpc('tools/list', {})
        for tool in result.get('tools', []):
            if tool.get('name') in ('load_model', 'get_job', 'generate_video', 'download_model', 'studio_status'):
                print(json.dumps({'name': tool['name'], 'inputSchema': tool['inputSchema']}, ensure_ascii=True))
    else:
        name = sys.argv[1]
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        if name == 'ltx-load':
            name = 'load_model'
            args = {'model': 'unsloth/LTX-2.5-GGUF', 'kind': 'video', 'variant': 'Q4_K_M',
                    'memory_mode': 'low_vram', 'speed_mode': 'off', 'wait_s': 50}
        elif name == 'ltx-status':
            name = 'get_job'
            args = {'kind': 'load', 'id': 'Jr070lfgeiZwDwpi', 'wait_s': 30}
        elif name == 'ltx-generate':
            name = 'generate_video'
            request = json.loads((ROOT / 'video' / 'full_motion' / 'anime-quality.wan-job.json').read_text())['request']
            args = {'prompt': request['prompt'], 'size': request['size'],
                    'first_frame': {'path': request['image']}, 'num_frames': 73,
                    'fps': 16, 'seed': request['seed']}
        elif name == 'ltx-video-status':
            name = 'get_job'
            args = {'kind': 'video', 'id': 'video_6d0b79878cf44478955b08f7c97d442e',
                    'wait_s': 30, 'return_media': 'link'}
        elif name == 'ltx-cancel':
            name = 'cancel'
            args = {'kind': 'video', 'id': 'video_6d0b79878cf44478955b08f7c97d442e'}
        result = api.rpc('tools/call', {'name': name, 'arguments': args})
        print(json.dumps(studio_mcp.safe(result, key), ensure_ascii=True))
finally:
    pass
