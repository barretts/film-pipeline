"""Download the local series writer GGUF; resume partial transfers, never overwrite silently."""
from pathlib import Path
import argparse
import httpx
ROOT=Path(__file__).resolve().parent.parent
REPO='unsloth/Qwen3.5-9B-GGUF';FILE='Qwen3.5-9B-UD-Q4_K_XL.gguf'
URL=f'https://huggingface.co/{REPO}/resolve/main/{FILE}'

def expected_size(client):
 response=client.get(f'https://huggingface.co/api/models/{REPO}/tree/main',follow_redirects=False)
 response.raise_for_status()
 for entry in response.json():
  if entry.get('path')==FILE:return int(entry.get('size') or entry.get('lfs',{}).get('size') or 0)
 raise RuntimeError('Writer file not listed on the Hub; refusing to download an unknown target')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--force',action='store_true',help='Re-download over an existing complete model file')
 args=parser.parse_args()
 target=ROOT/'local-runtime'/'models'/FILE;target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.gguf.part')
 with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as client:
  size=expected_size(client)
  if not size:raise RuntimeError('Hub metadata reported zero size for the writer model')
  if target.exists()and not args.force:
   if target.stat().st_size!=size:raise RuntimeError(f'Existing {FILE} has the wrong size; keep it, inspect it, or pass --force to replace')
   print('READY (cached)',target,target.stat().st_size,flush=True);return 0
  if target.exists()and args.force:target.unlink()
  start=tmp.stat().st_size if tmp.exists()else 0
  if start>size:raise RuntimeError('Partial file is larger than the model; preserve and inspect '+str(tmp))
  print('Downloading',FILE,'from byte',start,'of',size,flush=True)
  with client.stream('GET',URL,headers={'Range':f'bytes={start}-'}if start else{}) as response:
   response.raise_for_status()
   if start and response.status_code!=206:raise RuntimeError('Server refused range resume; preserve '+str(tmp))
   with tmp.open('ab' if start else'wb') as out:
    for block in response.iter_bytes(4*1024*1024):
     out.write(block)
     done=out.tell()
     if done%(64*1024*1024)<4*1024*1024:print(f'progress {done*100//size}%',flush=True)
  if tmp.stat().st_size!=size:raise RuntimeError(f'Download finished at {tmp.stat().st_size} bytes, expected {size}; preserve and resume {tmp}')
  tmp.replace(target)
 print('READY',target,target.stat().st_size,flush=True);return 0

if __name__=='__main__':
 raise SystemExit(main())
