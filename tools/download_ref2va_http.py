from pathlib import Path
import httpx,time,os
url='https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors'
out=Path(r'F:\film-pipeline\comfy-local\models\diffusion_models\minimax_h3_ref2va_pruned_int8_convrot.safetensors.part')
size=20970379616
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
out.replace(out.with_suffix(''))
print('DONE',n,flush=True)
