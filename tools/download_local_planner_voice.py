"""Download fixed local planner and voice assets; preserve and resume partial transfers."""
from pathlib import Path
import httpx,hashlib
r=Path(__file__).resolve().parent.parent/'local-runtime'/'models';r.mkdir(parents=True,exist_ok=True)
files=[('Qwen3.5-4B-Q4_K_M.gguf','https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/e87f176479d0855a907a41277aca2f8ee7a09523/Qwen3.5-4B-Q4_K_M.gguf','00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'),('en_US-amy-medium.onnx','https://huggingface.co/rhasspy/piper-voices/resolve/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/amy/medium/en_US-amy-medium.onnx','b3a6e47b57b8c7fbe6a0ce2518161a50f59a9cdd8a50835c02cb02bdd6206c18'),('en_US-amy-medium.onnx.json','https://huggingface.co/rhasspy/piper-voices/resolve/5041a7a49ae5b3a0f30e6837769eb03fdbb231bd/en/en_US/amy/medium/en_US-amy-medium.onnx.json','95a23eb4d42909d38df73bb9ac7f45f597dbfcde2d1bf9526fdeaf5466977d77')]
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as c:
 for name,url,sha in files:
  p=r/name;tmp=p.with_suffix(p.suffix+'.part')
  if p.exists():
   if digest(p)!=sha:raise RuntimeError('Existing file hash mismatch; do not overwrite: '+str(p))
  else:
   start=tmp.stat().st_size if tmp.exists() else 0;print('Downloading',name,'from byte',start,flush=True)
   with c.stream('GET',url,headers={'Range':f'bytes={start}-'} if start else {}) as resp:
    resp.raise_for_status()
    if start and resp.status_code!=206:raise RuntimeError('Server refused range resume; preserve '+str(tmp))
    with tmp.open('ab' if start else 'wb') as out:
     for block in resp.iter_bytes(4*1024*1024):out.write(block)
   if digest(tmp)!=sha:raise RuntimeError('Hash mismatch; preserve and inspect '+str(tmp))
   tmp.replace(p)
  print('READY',name,p.stat().st_size,sha,flush=True)
