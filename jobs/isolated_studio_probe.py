"""CPU-only isolated Studio startup probe; never loads or downloads a model."""
import os
from pathlib import Path
import runpy
import sys

root = Path(r'F:\film-pipeline\venvs\isolated-studio-probe')
backend = Path(r'C:\Users\barrett\.unsloth\studio\unsloth_studio\Lib\site-packages\studio\backend')
for directory in ('studio','hf/hub','cache','tmp','documents','projects','torch','triton','matplotlib'):
    (root / directory).mkdir(parents=True, exist_ok=True)
os.environ.update({
    'UNSLOTH_HOME':str(root),
    'UNSLOTH_STUDIO_HOME':str(root/'studio'),
    'UNSLOTH_STUDIO_DOCUMENTS_HOME':str(root/'documents'),
    'UNSLOTH_STUDIO_PROJECTS_HOME':str(root/'projects'),
    'HF_HOME':str(root/'hf'),
    'HF_HUB_CACHE':str(root/'hf/hub'),
    'HUGGINGFACE_HUB_CACHE':str(root/'hf/hub'),
    'HF_DATASETS_CACHE':str(root/'hf/datasets'),
    'TRANSFORMERS_CACHE':str(root/'hf/hub'),
    'XDG_CACHE_HOME':str(root/'cache'),
    'TORCH_HOME':str(root/'torch'),
    'TRITON_CACHE_DIR':str(root/'triton'),
    'MPLCONFIGDIR':str(root/'matplotlib'),
    'TEMP':str(root/'tmp'),
    'TMP':str(root/'tmp'),
    'PYTHONDONTWRITEBYTECODE':'1',
    'CUDA_VISIBLE_DEVICES':'',
    'UNSLOTH_STUDIO_NO_FILE_LOG':'1',
    'HF_HUB_OFFLINE':'1',
    'HF_HUB_DISABLE_TELEMETRY':'1',
    'DO_NOT_TRACK':'1',
})
os.environ.pop('UNSLOTH_API_KEY',None)
sys.dont_write_bytecode = True
sys.path.insert(0,str(backend))
sys.argv = ['run.py','--api-only','--host','127.0.0.1','--port','8894']
print('CPU-only isolation probe; root:',root,'port: 8894',flush=True)
runpy.run_path(str(backend/'run.py'),run_name='__main__')
