from pathlib import Path
import httpx,time,os,hashlib,sys
url='https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/e5eb578a89295337b8ff433a035929ce0279e0b6/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors'
out=Path(__file__).resolve().parent.parent/'comfy-local'/'models'/'diffusion_models'/'minimax_h3_ref2va_pruned_int8_convrot.safetensors.part'
size=20970379616
final=out.with_suffix('');expected='9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779'
if final.exists():
 h=hashlib.sha256()
 with final.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 if final.stat().st_size==size and h.hexdigest()==expected:
  print('Existing model verified:',final);sys.exit(0)
 raise RuntimeError('Existing model differs; stop without overwriting: '+str(final))
out.parent.mkdir(parents=True,exist_ok=True)
start=out.stat().st_size if out.exists() else 0
print('Starting at',start,'of',size,flush=True)
with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as c:
 with c.stream('GET',url,headers={'Range':f'bytes={start}-'} if start else {}) as r:
  r.raise_for_status()
  if start and r.status_code!=206: raise RuntimeError('Server did not honor resume range')
  print('HTTP',r.status_code,flush=True)
  with open(out,'ab' if start else 'wb') as f:
   n=start; last=n
   for b in r.iter_bytes(chunk_size=4*1024*1024):
    f.write(b); n+=len(b)
    if n-last>=512*1024*1024:
     f.flush();print('Downloaded',n,'/',size,flush=True);last=n
if n!=size: raise ValueError(f'Size mismatch {n} != {size}')
h=hashlib.sha256()
with out.open('rb') as f:
 for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
if h.hexdigest()!=expected:raise RuntimeError('Downloaded model hash mismatch; partial file preserved')
out.replace(final)
print('DONE',n,flush=True)
