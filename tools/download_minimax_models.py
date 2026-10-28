"""Download the official ComfyUI MiniMax H3 image-to-video components locally."""
import os
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'comfy-local'
os.environ['HF_HOME'] = str(ROOT / 'cache' / 'hf')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import httpx
from huggingface_hub import hf_hub_download, set_client_factory

set_client_factory(lambda: httpx.Client(trust_env=False, follow_redirects=True, timeout=120))
files = [
    'diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors',
    'text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors',
    'vae/minimax_h3_video_vae_fp16.safetensors',
    'vae/minimax_h3_audio_vae_fp32.safetensors',
    'loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors',
]
hashes={'diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors':'12944c1f7791637e7de12208aef04da82bd26b95271b1b47d817364315ade993','text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors':'35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6','vae/minimax_h3_video_vae_fp16.safetensors':'7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522','vae/minimax_h3_audio_vae_fp32.safetensors':'8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48','loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors':'2339acdf19bfe123f46b971ea35d367a84adb85de43627e1eceafa5a5b2b111e'}
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
for filename in files:
    target=ROOT/'models'/filename
    if target.exists():
        if digest(target)!=hashes[filename]:raise RuntimeError('Existing asset differs; stop without overwriting: '+str(target))
        print('VERIFIED',target,flush=True);continue
    print(f'Downloading {filename}', flush=True)
    result = hf_hub_download('Comfy-Org/MiniMax-H3', filename,
                             local_dir=ROOT / 'models', token=False, revision='e5eb578a89295337b8ff433a035929ce0279e0b6')
    if digest(Path(result))!=hashes[filename]:raise RuntimeError('Downloaded asset hash mismatch: '+result)
    print(f'Ready: {Path(result).name} ({Path(result).stat().st_size} bytes)', flush=True)
