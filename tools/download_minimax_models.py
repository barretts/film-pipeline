"""Download the official ComfyUI MiniMax H3 image-to-video components locally."""
import os
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
for filename in files:
    print(f'Downloading {filename}', flush=True)
    result = hf_hub_download('Comfy-Org/MiniMax-H3', filename,
                             local_dir=ROOT / 'models', token=False)
    print(f'Ready: {Path(result).name} ({Path(result).stat().st_size} bytes)', flush=True)
