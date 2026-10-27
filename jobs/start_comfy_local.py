"""Start the installed SwarmUI ComfyUI using project-local working directories."""
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent.parent / 'comfy-local'
source = Path(r'E:\SwarmUI\dlbackend\comfy\ComfyUI')
for name in ('input', 'output', 'temp', 'user', 'models', 'cache', 'torch', 'triton'):
    (root / name).mkdir(parents=True, exist_ok=True)
os.environ.update({'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
                   'TEMP': str(root / 'temp'), 'TMP': str(root / 'temp'),
                   'XDG_CACHE_HOME': str(root / 'cache'), 'HF_HOME': str(root / 'cache' / 'hf'),
                   'TORCH_HOME': str(root / 'torch'), 'TRITON_CACHE_DIR': str(root / 'triton')})
sys.dont_write_bytecode = True
sys.path.insert(0, str(source))
sys.argv = [str(source / 'main.py'), '--listen', '127.0.0.1', '--port', '8191',
            '--base-directory', str(root), '--disable-auto-launch', '--disable-all-custom-nodes',
            '--offline', '--lowvram', '--whitelist-custom-nodes', 'film_h3_audio']
runpy.run_path(str(source / 'main.py'), run_name='__main__')
