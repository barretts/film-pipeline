"""Download Piper voice models for series characters; fall back to existing voices when a name 404s."""
from pathlib import Path
import argparse
import httpx
ROOT=Path(__file__).resolve().parent.parent
MODELS=ROOT/'local-runtime'/'models'
BASE_URL='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US'
DEFAULT=['amy','ryan','kristin','billy','raymond','zoey']
# rhasspy/piper-voices tree API is not anonymous-readable; probe known en_US medium voices instead.
CANDIDATES=['joe','norman','sam','hfc_male','hfc_female','kristin','ryan','amy']

def paths(name):return MODELS/f'en_US-{name}-medium.onnx',MODELS/f'en_US-{name}-medium.onnx.json'

def exists(client,name):
 try:
  response=client.head(f'{BASE_URL}/{name}/medium/en_US-{name}-medium.onnx',follow_redirects=True)
  return response.status_code==200
 except httpx.HTTPError:return False

def fetch(client,name):
 onnx,jsonp=paths(name)
 if onnx.exists()and jsonp.exists():return onnx.name,'cached'
 states=[]
 for path,suffix in((onnx,'.onnx'),(jsonp,'.onnx.json')):
  tmp=path.with_name(path.name+'.part');url=f'{BASE_URL}/{name}/medium/{path.name}'
  start=tmp.stat().st_size if tmp.exists()else 0
  with client.stream('GET',url,headers={'Range':f'bytes={start}-'}if start else{},follow_redirects=True) as response:
   response.raise_for_status()
   if start and response.status_code not in(200,206):raise RuntimeError('Server refused range resume; preserve '+str(tmp))
   if start==200:tmp.unlink(missing_ok=True)
   with tmp.open('ab' if start and response.status_code==206 else'wb') as out:
    for block in response.iter_bytes(1024*1024):out.write(block)
  tmp.replace(path);states.append(suffix)
 return onnx.name,'downloaded'

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('voices',nargs='*',default=None)
 args=parser.parse_args();wanted=args.voices or DEFAULT
 table=[];used=set()
 with httpx.Client(trust_env=False,follow_redirects=True,timeout=120) as client:
  for slot in wanted:
   onnx,_=paths(slot)
   if onnx.exists():table.append((slot,slot,'cached'));used.add(slot);continue
   if exists(client,slot)and slot not in used:
    name,state=fetch(client,slot);used.add(slot);table.append((slot,name,state));continue
   replacement=next((c for c in CANDIDATES if c not in used and exists(client,c)),None)
   if not replacement:raise RuntimeError(f'No piper voice available for slot {slot}; check the voice list')
   name,state=fetch(client,replacement);used.add(replacement)
   print(f'Voice {slot!r} does not exist; substituted {name} for this slot',flush=True)
   table.append((slot,name,state))
 print(f'{"requested":<12}{"voice file":<32}state')
 for slot,name,state in table:print(f'{slot:<12}{name:<32}{state}')
 return 0

if __name__=='__main__':
 raise SystemExit(main())
