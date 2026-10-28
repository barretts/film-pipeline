from pathlib import Path
import httpx,hashlib
p=Path('local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf');u='https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf';tmp=p.with_suffix('.part')
with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as c:
 with c.stream('GET',u) as r:
  r.raise_for_status();print('HTTP',r.status_code,flush=True)
  with tmp.open('wb') as f:
   for b in r.iter_bytes(4*1024*1024):f.write(b)
tmp.replace(p);h=hashlib.sha256()
with p.open('rb') as f:
 for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
print('READY',p.stat().st_size,h.hexdigest(),flush=True)
