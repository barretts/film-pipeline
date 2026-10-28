"""Start the installed SwarmUI ComfyUI using project-local working directories."""
import os
from pathlib import Path
import runpy
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parent.parent / 'comfy-local'
source = Path(os.environ.get('LOCAL_FILM_COMFY', r'E:\SwarmUI\dlbackend\comfy\ComfyUI'))
if not (source / 'main.py').is_file():
    source = Path(__file__).resolve().parent.parent / 'local-runtime' / 'ComfyUI'
if not (source / 'main.py').is_file():
    raise FileNotFoundError('ComfyUI not found; set LOCAL_FILM_COMFY to its source directory')
for name in ('input', 'output', 'temp', 'user', 'models', 'cache', 'torch', 'triton'):
    (root / name).mkdir(parents=True, exist_ok=True)
os.environ.update({'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                   'TEMP': str(root / 'temp'), 'TMP': str(root / 'temp'),
                   'XDG_CACHE_HOME': str(root / 'cache'), 'HF_HOME': str(root / 'cache' / 'hf'),
                   'TORCH_HOME': str(root / 'torch'), 'TRITON_CACHE_DIR': str(root / 'triton')})
sys.dont_write_bytecode = True
sys.path.insert(0, str(source))
sys.path.insert(0, str(root / 'python-extra'))
sys.path.insert(0, str(root / 'python-cu130'))
sys.argv = [str(source / 'main.py'), '--listen', '127.0.0.1', '--port', '8191',
            '--base-directory', str(root), '--disable-auto-launch', '--disable-all-custom-nodes',
            '--offline', '--lowvram', '--whitelist-custom-nodes', 'film_h3_audio',
            'MiniMax_H3_Semantic_Bridge', 'ComfyUI-Ref2VA-VSA', 'ComfyUI-KJNodes',
            'Comfyui-Memory_Cleanup', 'ComfyUI-VideoHelperSuite', 'ComfyUI_Nvidia_VFX_Nodes']
runpy.run_path(str(source / 'main.py'), run_name='__main__')
