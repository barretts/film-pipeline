"""Verify required local runtime/model files; --hash also reads and hashes large weights."""
import argparse,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
files={
'local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf':(2740937888,'00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'),
'local-runtime/models/en_US-amy-medium.onnx':(63201294,'b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18'),
'local-runtime/models/en_US-amy-medium.onnx.json':(4882,'95a23eb4d42909d38df73bb9ac7f45f597dbfcde2d1bf9526fdeaf5466977d77'),
'comfy-local/models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors':(20970379616,'9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779'),
'comfy-local/models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors':(15687142551,'35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6'),
'comfy-local/models/vae/minimax_h3_video_vae_fp16.safetensors':(5207808496,'7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'),
'comfy-local/models/vae/minimax_h3_audio_vae_fp32.safetensors':(605254808,'8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48'),
'comfy-local/models/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors':(1956193000,'5b9ab5ade15d0775676d01a907268a69a1468dc6033b3b0d3ded5502f3ebb84c'),
'comfy-local/models/loras/fasth3_vsa_gate.safetensors':(3853522616,'bf95408e335c4b0d6a1a44946a428a3e12849e6eab2de9566ecedae4a0043420'),
'comfy-local/models/semantic_bridge/MiniMaxH3_SemanticBridge_v1.safetensors':(11023032,'ac0dc8ac05f545ebdee12e2fcebe4515b049f9cfd9558eb4887a9bf3fd6d562e')}
optional={
'comfy-local/models/diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors':(20958205608,'12944c1f7791637e7de12208aef04da82bd26b95271b1b47d817364315ade993'),
'comfy-local/models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors':(1956193000,'2339acdf19bfe123f46b971ea35d367a84adb85de43627e1eceafa5a5b2b111e')}
def main():
 p=argparse.ArgumentParser();p.add_argument('--hash',action='store_true');p.add_argument('--fallback',action='store_true');a=p.parse_args();items=dict(files)
 if a.fallback:items.update(optional)
 failures=[]
 for name,(size,expected) in items.items():
  path=ROOT/name
  if not path.is_file() or path.stat().st_size!=size:failures.append(name+': missing or wrong size');continue
  if a.hash:
   h=hashlib.sha256()
   with path.open('rb') as f:
    for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
   if h.hexdigest()!=expected:failures.append(name+': SHA-256 mismatch');continue
  print('OK',name,flush=True)
 for exe in ['local-runtime/llama/llama-server.exe','local-runtime/piper/piper/piper.exe']:
  if not (ROOT/exe).is_file():failures.append(exe+': missing')
 for failure in failures:print('FAIL',failure,flush=True)
 if failures:raise SystemExit(1)
 print('Verified',len(items),'assets','with SHA-256' if a.hash else 'by size only')
if __name__=='__main__':main()
