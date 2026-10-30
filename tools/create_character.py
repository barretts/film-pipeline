#!/usr/bin/env python3
"""Character tools: piper voice auditions and character creation (portrait + orbit refs)."""
import argparse,json,os,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
for p in (str(ROOT),str(ROOT/'tools')):sys.path.insert(0,p) if p not in sys.path else None
from local_film import pipeline as P,series as S,characters as REG
from local_film.pipeline import JobError
SERIES=S.SERIES;RUNTIME=P.RUNTIME
AUDITION='The signal was clear tonight. I followed it to the door.'
ORBIT='The portrait subject slowly turns their head from profile to face the camera, then back, expression calm, identical clothing and framing, static camera.'
SEEDS=(7701,7702,7703)

def voices():return sorted(p.stem[len('en_US-'):-len('-medium')]for p in (RUNTIME/'models').glob('en_US-*-medium.onnx'))

def piper_synth(voice,text,target):
 exe=RUNTIME/'piper'/'piper'/'piper.exe';model=RUNTIME/'models'/f'en_US-{voice}-medium.onnx'
 if not exe.is_file():raise JobError('Piper executable missing; see installation guide')
 if not model.is_file():raise JobError('Voice not downloaded: '+voice+' (run tools/download_piper_voices.py)')
 temp=target.with_name(target.stem+'.partial.wav')
 result=subprocess.run([str(exe),'--model',str(model),'--output_file',str(temp)],input=text+'\n',text=True,encoding='utf8',capture_output=True,timeout=300)
 if result.returncode or not temp.is_file():raise JobError('Piper failed for '+voice+': '+result.stderr[-500:])
 os.replace(temp,target)

def audition(a):
 slug=S.slugify(a.name);directory=SERIES/'characters'/slug;directory.mkdir(parents=True,exist_ok=True)
 selected=[a.voice] if a.voice else voices()
 if not selected:raise JobError('No en_US-*-medium.onnx voices in local-runtime/models; run tools/download_piper_voices.py')
 made=[]
 for voice in selected:
  target=directory/f'audition-{voice}.wav'
  if not target.exists():piper_synth(voice,AUDITION,target)
  made.append(target)
 print('Auditions for',slug+':')
 for path in made:print(' ',path,f'({P.duration(path):.2f}s)')
 print('Owner: listen and rerun --create with --voice <chosen>.')

def gpu_free():
 try:return int(P.run_cmd(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits']).stdout.decode().strip().splitlines()[0])
 except Exception as e:raise JobError('Cannot query GPU memory with nvidia-smi') from e

def generate_portraits(directory,name,description,appearance,style):
 from studio_mcp import Studio,key_from_environment,record_call
 import urllib.parse,urllib.request
 from PIL import Image
 key=key_from_environment();studio=Studio(key,timeout=300)
 def call(n,arguments):
  start=time.time()
  try:
   response=studio.rpc('tools/call',{'name':n,'arguments':arguments});ok=not response.get('isError',False)
  except Exception as exc:
   response,ok={'error':str(exc).replace(key,'<redacted>')},False
  record_call(n,arguments,response,start,time.time(),key,ok)
  if not ok:raise JobError(f'Studio {n} failed; see tools/mcp-log.jsonl')
  return response.get('structuredContent',{})
 prompt=(f'Original character reference portrait photograph: {name}. {description} {appearance}. '
  'Head-and-shoulders framing facing camera, plain neutral background, calm expression, '
  f'no text, no watermark. Visual style: {style}.')
 paths=[]
 try:
  response=call('load_model',{'kind':'image','model':'unsloth/FLUX.2-klein-4B','memory_mode':'low_vram','transformer_quant':'auto','wait_s':50})
  job=None
  while response.get('status') in ('loading','running','pending'):
   job=response.get('job_id') or response.get('id') or job
   if not job:raise JobError('Model load still active without job ID; inspect Studio before retrying')
   response=call('get_job',{'kind':'load','id':job,'wait_s':50})
   if response.get('status')=='completed':response=response.get('load') or {}
  if not response.get('loaded'):raise JobError('Image model did not report a completed load')
  for index,seed in enumerate(SEEDS,1):
   response=call('generate_image',{'prompt':prompt,'width':704,'height':1280,'steps':4,'guidance':1.0,'seed':seed,'return_media':'link'})
   images=response.get('images') or []
   if len(images)!=1:raise JobError(f'Expected one image for candidate {index}')
   url=images[0].get('url') or images[0].get('download_url')
   parsed=urllib.parse.urlsplit(url or '')
   if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.port!=8888:raise JobError('Unexpected Studio image URL; refusing nonlocal transfer')
   request=urllib.request.Request(url,headers={'Authorization':'Bearer '+key})
   with studio.opener.open(request,timeout=120) as server:content=server.read()
   target=directory/f'portrait-candidate-{index}.png';temp=directory/f'.candidate-{index}.partial.png'
   temp.write_bytes(content)
   with Image.open(temp) as image:image.verify()
   os.replace(temp,target);paths.append(target)
   print('candidate:',target)
 finally:
  try:call('unload_model',{'kind':'image'})
  except Exception:pass
 return paths

def ms_cli(*args):return subprocess.run([sys.executable,str(ROOT/'tools'/'minimax_speech.py')]+[str(a)for a in args],capture_output=True,text=True,encoding='utf8',errors='replace',cwd=ROOT)

def orbit_refs(directory,portrait):
 silence=RUNTIME/'silence-3s.wav'
 if not silence.is_file():P.run_cmd(['ffmpeg','-y','-v','error','-f','lavfi','-i','anullsrc=r=22050:cl=mono','-t','3',silence])
 free=gpu_free()
 if free<12000:raise JobError(f'Only {free} MiB of GPU memory free; the turning-ref render needs 12000 MiB. Stopping Strata is allowed per repo policy; stop it and rerun.')
 refs=directory/'refs';refs.mkdir(exist_ok=True)
 def submit(name):
  result=ms_cli('submit','--name',name,'--image',portrait,'--audio',silence,'--prompt',ORBIT,'--frames',73,'--allow-trailing-silence')
  if result.returncode:raise JobError('Orbit submit failed: '+(result.stderr or result.stdout)[-500:])
 def outcome(name):
  result=ms_cli('status','--name',name)
  if result.returncode:raise JobError('Orbit status failed: '+(result.stderr or result.stdout)[-500:])
  data=json.loads(result.stdout);outputs=[]
  for items in (data.get('outputs') or {}).values():
   for m in items if isinstance(items,list) else []:
    if isinstance(m,dict) and m.get('filename'):outputs.append(P.BASE/'output'/str(m.get('subfolder') or '')/m['filename'])
  return data.get('status'),outputs
 name=f'{directory.name}-orbit';submit(name);attempts=1
 deadline=time.time()+3600
 while time.time()<deadline:
  status,outputs=outcome(name)
  if status=='success':
   videos=[o for o in outputs if str(o).lower().endswith('.mp4') and Path(o).is_file()] or sorted((P.BASE/'output').rglob(f'{directory.name}-orbit*.mp4'))
   if not videos:raise JobError('Orbit render completed without an mp4 output')
   P.run_cmd(['ffmpeg','-y','-v','error','-i',videos[0],'-vf','fps=1','-vsync','vfr',refs/'frame-%02d.png'])
   frames=sorted(refs.glob('frame-*.png'))
   if len(frames)<2:raise JobError('Orbit clip produced too few reference frames')
   return [f'refs/{f.name}'for f in frames[:3]],'orbit'
  if status=='error':
   if attempts>=2:raise JobError('Orbit render failed twice; see comfy-local/speech-jobs/'+name+'.json')
   attempts+=1;name=f'{directory.name}-orbit-retry{attempts}';submit(name)
  time.sleep(15)
 raise JobError('Timed out after one hour waiting for the orbit render; it may still be running (comfy-local/speech-jobs)')

def fallback_refs(directory,portrait):
 # No motion orbit: static framed crops of the approved portrait still give the
 # reference chain several looks at the face.
 from PIL import Image
 refs=directory/'refs';refs.mkdir(exist_ok=True)
 image=Image.open(portrait).convert('RGB');w,h=image.size;made=[]
 for index,(box,scale) in enumerate((('full',1.0),('center',1.18),('face',1.45)),1):
  if box=='full':crop=image
  else:
   cw,ch=int(w/scale),int(h/scale);left=(w-cw)//2;top=int(h*0.12) if box=='face' else (h-ch)//2
   crop=image.crop((left,top,left+cw,top+ch)).resize((w,h))
  path=refs/f'frame-{index:02d}.png';crop.save(path);made.append(f'refs/{path.name}')
 return made,'portrait-only'

def create(a):
 slug=S.slugify(a.name);directory=SERIES/'characters'/slug
 if (directory/'character.json').exists():raise JobError('Character exists: '+str(directory))
 if not a.voice:raise JobError('--voice is required for --create')
 if f'en_US-{a.voice}-medium.onnx' not in [p.name for p in (RUNTIME/'models').glob('en_US-*-medium.onnx')]:raise JobError('Voice not downloaded: '+a.voice+'; run tools/download_piper_voices.py and --audition first')
 directory.mkdir(parents=True,exist_ok=True)
 if a.portrait:
  portrait=Path(a.portrait)
  if not portrait.is_file():raise JobError('Portrait file missing: '+str(portrait))
  portrait=portrait.resolve();target=directory/'portrait.png'
  if portrait!=target:shutil.copyfile(portrait,target)
 else:
  style=a.style or 'Cinematic realism, 35mm film grain.'
  generate_portraits(directory,a.name,a.description,a.appearance,style)
  print('Owner approval required: rerun with --portrait <chosen candidate file> to finish creation.')
  return  # refuse to create character.json without an approved portrait
 try:frames,mode=orbit_refs(directory,directory/'portrait.png')
 except JobError as e:
  print('WARNING: '+str(e)+' Falling back to static framed crops of the approved portrait.',flush=True)
  frames,mode=fallback_refs(directory,directory/'portrait.png')
 sample=directory/f'audition-{a.voice}.wav'
 if not sample.exists():piper_synth(a.voice,AUDITION,sample)
 character={'id':slug,'name':a.name,'description':a.description,'appearance':a.appearance,'voice_model':f'en_US-{a.voice}-medium.onnx','voice_sample':sample.name,'portrait':'portrait.png','ref_images':['portrait.png']+frames,'ref_mode':mode}
 P.atomic(directory/'character.json',character)
 REG.load_character(SERIES,slug)
 for show_id in [x.strip()for x in (a.add_to_show or '').split(',')if x.strip()]:
  show_path=SERIES/show_id/'show.json'
  if not show_path.is_file():raise JobError('Unknown show for --add-to-show: '+show_id)
  show=json.loads(show_path.read_text(encoding='utf8'))
  if slug not in show.get('characters',[]):show['characters'].append(slug);P.atomic(show_path,show)
  print('Added',slug,'to show',show_id)
 print('Character created:',directory/f'character.json',f'(refs: {mode})')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--name',required=True)
 mode=ap.add_mutually_exclusive_group(required=True)
 mode.add_argument('--audition',action='store_true')
 mode.add_argument('--create',action='store_true')
 ap.add_argument('--voice');ap.add_argument('--description');ap.add_argument('--appearance')
 ap.add_argument('--style');ap.add_argument('--portrait');ap.add_argument('--add-to-show')
 a=ap.parse_args()
 try:
  if a.audition:audition(a)
  else:
   if not a.description or not a.appearance:raise JobError('--description and --appearance are required for --create')
   create(a)
 except JobError as x:
  print('ERROR:',x,file=sys.stderr);sys.exit(1)

if __name__=='__main__':main()
