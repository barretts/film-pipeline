import os
from pathlib import Path
root=Path(r'F:\film-pipeline\comfy-local')
os.environ['HF_HOME']=str(root/'cache'/'hf')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
import httpx
from huggingface_hub import hf_hub_download,set_client_factory
set_client_factory(lambda: httpx.Client(trust_env=False,follow_redirects=True,timeout=120))
files=[('Comfy-Org/MiniMax-H3','diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors',root/'models'),('lightx2v/Minimax-h3-Turbo','minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors',root/'models'/'loras'),('barelymining/ComfyUI-MiniMax-H3-FastVideo','fasth3_vsa_gate.safetensors',root/'models'/'loras'),('speach1sdef178/MiniMax-H3-Semantic-Bridge','MiniMaxH3_SemanticBridge_v1.safetensors',root/'models'/'semantic_bridge'),('speach1sdef178/MiniMax-H3-Semantic-Bridge','MiniMax_H3_Semantic_Bridge_v1.0.zip',root/'downloads')]
for repo,name,dest in files:
 print('Downloading',repo,name,flush=True)
 try:
  p=hf_hub_download(repo,name,local_dir=dest,token=False);print('READY',p,Path(p).stat().st_size,flush=True)
 except Exception as e: print('FAILED',repo,name,repr(e),flush=True)
