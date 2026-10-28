import os,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent/'comfy-local'
os.environ['HF_HOME']=str(root/'cache'/'hf')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN']='1'
import httpx
from huggingface_hub import hf_hub_download,set_client_factory
set_client_factory(lambda: httpx.Client(trust_env=False,follow_redirects=True,timeout=120))
files=[('Comfy-Org/MiniMax-H3','diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors',root/'models'),('lightx2v/Minimax-h3-Turbo','minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors',root/'models'/'loras'),('barelymining/ComfyUI-MiniMax-H3-FastVideo','fasth3_vsa_gate.safetensors',root/'models'/'loras'),('speach1sdef178/MiniMax-H3-Semantic-Bridge','MiniMaxH3_SemanticBridge_v1.safetensors',root/'models'/'semantic_bridge'),('speach1sdef178/MiniMax-H3-Semantic-Bridge','MiniMax_H3_Semantic_Bridge_v1.0.zip',root/'downloads')]
revisions={'Comfy-Org/MiniMax-H3':'e5eb578a89295337b8ff433a035929ce0279e0b6','lightx2v/Minimax-h3-Turbo':'30f485ed874aa44c8183348ad361c5eabad318da','barelymining/ComfyUI-MiniMax-H3-FastVideo':'aa554050fe27ec3c62e20e57519beb46741c9000','speach1sdef178/MiniMax-H3-Semantic-Bridge':'b9fe58ba6f428d990a59f20f09f719c8fbc67f7d'}
hashes={'minimax_h3_ref2va_pruned_int8_convrot.safetensors':'9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779','minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors':'5b9ab5ade15d0775676d01a907268a69a1468dc6033b3b0d3ded5502f3ebb84c','fasth3_vsa_gate.safetensors':'bf95408e335c4b0d6a1a44946a428a3e12849e6eab2de9566ecedae4a0043420','MiniMaxH3_SemanticBridge_v1.safetensors':'ac0dc8ac05f545ebdee12e2fcebe4515b049f9cfd9558eb4887a9bf3fd6d562e','MiniMax_H3_Semantic_Bridge_v1.0.zip':'c4866a0cc554237046814c9cb827a5960caecbd2214d5a5a04b0e43716b437bb'}
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
for repo,name,dest in files:
 existing=dest/name;expected=hashes[Path(name).name]
 if existing.exists():
  if digest(existing)!=expected:raise RuntimeError('Existing asset differs; stop without overwriting: '+str(existing))
  print('VERIFIED',existing,flush=True);continue
 print('Downloading',repo,name,flush=True)
 try:
  p=hf_hub_download(repo,name,local_dir=dest,token=False,revision=revisions[repo]);
  if digest(Path(p))!=expected:raise RuntimeError('Downloaded asset hash mismatch: '+p)
  print('READY',p,Path(p).stat().st_size,flush=True)
 except Exception as e:
  print('FAILED',repo,name,repr(e),flush=True)
  raise
