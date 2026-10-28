import httpx
from pathlib import Path
p=Path(__file__).resolve().parent.parent/'comfy-local'/'downloads'/'torch-2.11.0+cu130-cp313-cp313-win_amd64.whl';p.parent.mkdir(exist_ok=True)
u='https://download.pytorch.org/whl/cu130/torch-2.11.0%2Bcu130-cp313-cp313-win_amd64.whl'
with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as c:
 with c.stream('GET',u) as r:
  r.raise_for_status();print('HTTP',r.status_code,flush=True)
  with p.open('wb') as f:
   n=0;last=0
   for b in r.iter_bytes(chunk_size=4*1024*1024):
    f.write(b);n+=len(b)
    if n-last>=256*1024*1024:print('Downloaded',n,flush=True);last=n
print('DONE',n,flush=True)
