"""Unattended local film jobs: plan, synthesize, render, assemble and review."""
import argparse,contextlib,copy,hashlib,json,math,os,re,secrets,shutil,struct,subprocess,sys,tempfile,time,urllib.request,urllib.error,uuid
from pathlib import Path
from . import planner
from .references import character_reference_guidance
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'comfy-local';JOBS=ROOT/'local-film-jobs';RUNTIME=ROOT/'local-runtime';FPS=24;FRAMES=124;SEGMENT=FRAMES/FPS
FFMPEG_BIN=RUNTIME/'ffmpeg'/'ffmpeg-8.0.1-essentials_build'/'bin'
if FFMPEG_BIN.is_dir():os.environ['PATH']=str(FFMPEG_BIN)+os.pathsep+os.environ.get('PATH','')
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}));ADDR='http://127.0.0.1:8191'
class JobError(RuntimeError):pass
class JobCancelled(JobError):pass
def check_cancel(job):
 if (job/'cancel-request.json').exists():raise JobCancelled('Cancellation requested')

def atomic(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.state-',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf8') as f:json.dump(obj,f,indent=2,ensure_ascii=False);f.flush();os.fsync(f.fileno())
  for attempt in range(6):
   try:os.replace(tmp,path);break
   except PermissionError:
    if os.name!='nt' or attempt==5:raise
    time.sleep(0.05*(2**attempt))
 finally:
  if os.path.exists(tmp):os.unlink(tmp)

def load(p):return json.loads(p.read_text(encoding='utf8'))
def api(path,payload=None):
 body=None if payload is None else json.dumps(payload).encode();req=urllib.request.Request(ADDR+path,data=body,headers={'Content-Type':'application/json'})
 try:
  with OPENER.open(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise JobError('ComfyUI rejected request: '+e.read().decode(errors='replace')[:1200]) from e

def run_cmd(args,**kwargs):return subprocess.run([str(x) for x in args],check=True,capture_output=True,**kwargs)
def media(path):
 return json.loads(run_cmd(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height,sample_rate:format=duration','-of','json',path]).stdout)
def duration(path):return float(media(path)['format']['duration'])
def hash_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()

@contextlib.contextmanager
def locked(path,wait=False):
 path.parent.mkdir(parents=True,exist_ok=True);f=path.open('a+b');f.seek(0,2)
 if f.tell()==0:f.write(b'0');f.flush()
 f.seek(0);acquired=False
 try:
  if os.name=='nt':
   import msvcrt
   while True:
    try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);acquired=True;break
    except OSError:
     if not wait:raise JobError('Another process owns '+str(path))
     time.sleep(5)
  else:
   import fcntl
   fcntl.flock(f,fcntl.LOCK_EX|(0 if wait else fcntl.LOCK_NB));acquired=True
  yield
 finally:
  try:
   f.seek(0)
   if acquired and os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   elif acquired:fcntl.flock(f,fcntl.LOCK_UN)
  except OSError:pass
  f.close()

def script_parts(script):
 paragraphs=[p.strip() for p in re.split(r'\n\s*\n',script.strip()) if p.strip()]
 if not paragraphs:raise JobError('Script must not be empty')
 parts=[]
 for p in paragraphs:
  if len(p)<=450:parts.append(p);continue
  sentences=re.split(r'(?<=[.!?])\s+',p);cur=''
  for sentence in sentences:
   if len(sentence)>450:raise JobError('A script sentence is too long; break it into shorter sentences')
   if cur and len(cur)+len(sentence)+1>450:parts.append(cur);cur=''
   cur=(cur+' '+sentence).strip()
  if cur:parts.append(cur)
 if len(parts)>12:raise JobError('More than 12 script parts; split this request into smaller jobs')
 return parts

def local_path(value):
 text=str(value)
 if text.startswith(('\\\\','//')) or '://' in text:raise JobError('Only local file paths are allowed')
 path=Path(text).expanduser().resolve()
 if os.name=='nt':
  import ctypes
  if ctypes.windll.kernel32.GetDriveTypeW(path.anchor)==4:raise JobError('Network drives are not supported; copy the file locally')
 return path

def validate(req):
 for k in ['brief','script','style']:
  if not isinstance(req.get(k),str) or not req[k].strip():raise JobError(k+' is required')
 if len(req['brief'])>4000 or len(req['script'])>6000 or len(req['style'])>300:raise JobError('Brief, script or style exceeds the local planner limit')
 instructions=req.get('segment_instructions','')
 if not isinstance(instructions,str) or len(instructions)>2000:raise JobError('Instructions for every segment must be text of at most 2000 characters')
 req['segment_instructions']=instructions
 creativity=req.get('reference_creativity',0)
 if type(creativity) not in (int,float) or not math.isfinite(creativity) or not 0<=creativity<=100:raise JobError('Character reference creativity must be a number from 0 to 100')
 frames=req.get('segment_frames',FRAMES);overlap=req.get('continuation_overlap_frames',0)
 if type(frames) is not int or frames not in (124,141):raise JobError('Segment frames must be 124 or 141')
 if type(overlap) is not int or overlap not in (0,22):raise JobError('Continuation overlap must be 0 or 22 frames')
 seed_mode=req.get('seed_mode','custom' if 'seed' in req else 'random')
 if seed_mode not in ('random','custom'):raise JobError('Seed mode must be random or custom')
 if seed_mode=='custom' or req.get('seed') is not None:
  seed=req.get('seed')
  if type(seed) is not int or not 0<=seed<=4294967295:raise JobError('Seed must be a whole number from 0 to 4294967295')
 w=int(req.get('width',1080));h=int(req.get('height',1920));fps=int(req.get('fps',24))
 if not (256<=w<=3840 and 256<=h<=3840 and w%2==0 and h%2==0):raise JobError('Output dimensions must be even and between 256 and 3840')
 if fps not in (24,25,30):raise JobError('Output fps must be 24, 25, or 30')
 refs=req.get('references',[])
 if not isinstance(refs,list) or len(refs)>12:raise JobError('references must be a list of at most 12 local paths')
 for ref in refs:
  p=local_path(ref)
  if not p.is_file() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise JobError('Invalid reference image: '+str(p))
 obj=req.get('object_reference','').strip()
 if obj:
  p=local_path(obj)
  if not p.is_file() or p.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise JobError('Invalid object reference image: '+str(p))
 description=req.get('object_description','').strip()
 if len(description)>500:raise JobError('Object description is too long')
 req.update(object_reference=obj,object_description=description)
 music=req.get('music')
 if music and not local_path(music).is_file():raise JobError('Music file does not exist')
 target=float(req.get('duration_seconds',0) or 0)
 if not math.isfinite(target) or target<0 or target>180:raise JobError('Duration must be 0 (automatic) or at most 180 seconds')
 before=float(req.get('speech_before_seconds',0) or 0);after=float(req.get('speech_after_seconds',0) or 0)
 if not all(math.isfinite(x) and 0<=x<=30 for x in (before,after)):raise JobError('Speech pauses must each be between 0 and 30 seconds')
 req.update(width=w,height=h,fps=fps,duration_seconds=target,references=refs,speech_before_seconds=before,speech_after_seconds=after)
 return req

def create(req):
 req=validate(req);req['seed_mode']=req.get('seed_mode','custom' if 'seed' in req else 'random')
 if req['seed_mode']=='random':req['seed']=secrets.randbelow(4294967296)
 JOBS.mkdir(parents=True,exist_ok=True);ident=time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8];job=JOBS/ident;job.mkdir()
 refs=[]
 for i,ref in enumerate(req['references']):
  source=local_path(ref);dest=job/'references'/f'{i:02}{source.suffix.lower()}';dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest);refs.append({'path':str(dest),'original':str(source),'sha256':hash_file(dest)})
 req['staged_references']=refs
 if req['object_reference']:
  source=local_path(req['object_reference']);dest=job/'references'/('object'+source.suffix.lower());dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest);req['staged_object_reference']={'path':str(dest),'original':str(source),'sha256':hash_file(dest)}
 if req.get('music'):
  source=local_path(req['music']);dest=job/'music'/('source'+source.suffix.lower());dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest);req['staged_music']=str(dest)
 atomic(job/'request.json',req);atomic(job/'state.json',{'job_id':ident,'status':'created','created':time.time(),'seed_mode':req['seed_mode'],'seed':req['seed'],'segments':{},'events':[]})
 return job

def log(state,event,**kw):state['events'].append({'time':time.time(),'event':event,**kw})
def save(job,state):atomic(job/'state.json',state)

def make_plan(job,state):
 if (job/'plan.json').exists():return load(job/'plan.json')
 req=load(job/'request.json');parts=script_parts(req['script']);state['status']='planning';save(job,state)
 started=time.time();result=planner.plan(req['brief'],parts,req['style'],job/'planner.log',has_reference=bool(req['staged_references']),segment_instructions=req.get('segment_instructions',''),reference_creativity=req.get('reference_creativity',0))
 shots=[]
 for i,(text,visual) in enumerate(zip(parts,result['shots'])):
  shots.append({'id':f'shot-{i+1:02}','narration':text,'character':result['character'],**visual,'estimated_seconds':max(2,round(len(text.split())/2.5,1)),'continuation_boundaries_seconds':[]})
 plan={'brief':req['brief'],'style':req['style'],'segment_instructions':req.get('segment_instructions',''),'planner_model':'Qwen3.5-4B-Instruct Q4_K_M','shots':shots,'created':time.time()}
 atomic(job/'plan.json',plan);log(state,'plan_created',shots=len(shots),seconds=round(time.time()-started,2));save(job,state);return plan

def voice(job,state,plan):
 exe=RUNTIME/'piper'/'piper'/'piper.exe';model=RUNTIME/'models'/'en_US-amy-medium.onnx'
 if not exe.is_file() or not model.is_file():raise JobError('Piper executable or voice missing; see installation guide')
 req=load(job/'request.json');before=float(req.get('speech_before_seconds',0) or 0);after=float(req.get('speech_after_seconds',0) or 0)
 for shot in plan['shots']:
  target=job/'voices'/f"{shot['id']}.wav";target.parent.mkdir(exist_ok=True)
  hash_input=shot['narration'] if not before and not after else json.dumps([shot['narration'],before,after],ensure_ascii=False)
  text_hash=hashlib.sha256(hash_input.encode('utf8')).hexdigest();known=state.setdefault('voice_text_hashes',{}).get(shot['id'])
  if target.exists() and known!=text_hash:raise JobError('Existing voice does not match current narration; create a new job or inspect the interruption')
  if not target.exists():
   temp=target.with_name(target.stem+'.partial.wav');start=time.time()
   p=subprocess.run([str(exe),'--model',str(model),'--output_file',str(temp)],input=shot['narration']+'\n',text=True,encoding='utf8',capture_output=True,timeout=300)
   if p.returncode or not temp.is_file():raise JobError('Piper failed: '+p.stderr[-1000:])
   if duration(temp)<=0.2:raise JobError('Piper produced empty audio')
   if before or after:
    padded=target.with_name(target.stem+'.padded.partial.wav')
    run_cmd(['ffmpeg','-y','-v','error','-i',temp,'-af',f'adelay={round(before*1000)}:all=1,apad=pad_dur={after}','-c:a','pcm_s16le',padded])
    if duration(padded)+0.03<duration(temp)+before+after:raise JobError('Padded speech is truncated')
    os.replace(padded,target);temp.unlink()
   else:os.replace(temp,target)
   state['voice_text_hashes'][shot['id']]=text_hash;log(state,'voice_ready',shot=shot['id'],seconds=round(time.time()-start,2));save(job,state)
  shot['voice']=str(target);shot['voice_seconds']=duration(target)
 req=load(job/'request.json');minimum=sum(s['voice_seconds']+0.25 for s in plan['shots']);target=req['duration_seconds'] or minimum
 if target+0.05<minimum:raise JobError(f'Requested duration {target:.2f}s is shorter than narration ({minimum:.2f}s); increase duration')
 extra=target-minimum
 for s in plan['shots']:
  s['duration_seconds']=s['voice_seconds']+0.25+extra*(s['voice_seconds']+0.25)/minimum
  s['continuation_boundaries_seconds']=[round(part['timeline_start'],3) for part in segment_schedule(s['duration_seconds'],req)[1:]]
 atomic(job/'plan.json',plan);return plan

def segment_schedule(seconds,req):
 span=req.get('segment_frames',FRAMES)/FPS;overlap=req.get('continuation_overlap_frames',0)/FPS
 count=1+math.ceil(max(0,seconds-span)/(span-overlap));parts=[]
 for i in range(count):
  start=i*(span-overlap);trim=overlap if i else 0;timeline=start+trim
  parts.append({'index':i,'audio_start':start,'trim_start':trim,'timeline_start':timeline,'seconds':min(span-trim,seconds-timeline)})
 return parts

def internal_size(w,h):
 if w==1080 and h==1920:return 704,1280
 ratio=w/h;area=704*1280; iw=max(32,round(math.sqrt(area*ratio)/32)*32);ih=max(32,round(math.sqrt(area/ratio)/32)*32)
 return min(iw,1536),min(ih,1536)

def ensure_server():
 def check():
  data=api('/system_stats');args=data.get('system',{}).get('argv',[])
  if '--base-directory' not in args or args.index('--base-directory')+1>=len(args) or Path(args[args.index('--base-directory')+1]).resolve()!=BASE.resolve():
   raise JobError('Port 8191 is occupied by a ComfyUI outside this project; do not alter it. Resolve the port conflict first.')
  obj=api('/object_info');required=['MiniMaxH3DistilledImageToVideo','Ref2VAVSAGatePatch','LCH3AudioSync','VHS_VideoCombine','ImageResizeKJv2']
  missing=[x for x in required if x not in obj]
  if missing:raise JobError('ComfyUI missing required nodes: '+', '.join(missing))
  return data
 try:return check()
 except urllib.error.URLError:pass
 with locked(JOBS/'comfy-start.lock',wait=True):
  try:return check()
  except urllib.error.URLError:pass
  choices=[os.environ.get('LOCAL_FILM_COMFY_PYTHON',''),str(RUNTIME/'venv'/'Scripts'/'python.exe'),r'E:\SwarmUI\dlbackend\comfy\ComfyUI\venv\Scripts\python.exe']
  python=next((Path(x) for x in choices if x and Path(x).is_file()),None)
  if not python:raise JobError('No ComfyUI Python found; set LOCAL_FILM_COMFY_PYTHON or install local-runtime/venv')
  log_path=JOBS/'comfy-server.log'
  with log_path.open('ab') as f:proc=subprocess.Popen([str(python),str(ROOT/'jobs'/'start_comfy_local.py')],cwd=str(ROOT),stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  deadline=time.time()+180
  while time.time()<deadline:
   if proc.poll() is not None:raise JobError('ComfyUI startup failed; inspect '+str(log_path))
   try:return check()
   except urllib.error.URLError:time.sleep(3)
  raise JobError('ComfyUI did not start within 180 seconds; inspect '+str(log_path))

def wait_idle(state,job):
 deadline=time.time()+7200;unloaded=False
 while time.time()<deadline:
  check_cancel(job)
  q=api('/queue')
  if not q.get('queue_running') and not q.get('queue_pending'):
   if not unloaded:
    try:api('/free',{'unload_models':True,'free_memory':True})
    except Exception:pass
    unloaded=True
   try:
    r=run_cmd(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits']);free=int(r.stdout.decode().strip().splitlines()[0])
   except Exception as e:raise JobError('Cannot query NVIDIA GPU memory with nvidia-smi') from e
   if free>=12000:return
   state['gpu_free_mib']=free
  if state.get('status')!='waiting_for_gpu':state['status']='waiting_for_gpu';save(job,state)
  time.sleep(10)
 raise JobError('Timed out after two hours waiting for an idle ComfyUI and 12000 MiB free GPU memory')

def locate(id):
 history=api('/history/'+id)
 if id in history:return 'history',history[id]
 q=api('/queue')
 for key in ('queue_running','queue_pending'):
  if any(len(x)>1 and x[1]==id for x in q.get(key,[])):return key,None
 return 'unknown',None

def render_segment(job,state,shot,index,ref,req,motion_ref=None):
 check_cancel(job)
 key=f"{shot['id']}-{index:02}";record=state['segments'].get(key);outfile=job/'segments'/f'{key}.mp4';outfile.parent.mkdir(exist_ok=True)
 if outfile.exists():
  try:
   if duration(outfile)>0 and any(x['codec_type']=='audio' for x in media(outfile)['streams']):return outfile
  except Exception:raise JobError('Existing segment is invalid; do not overwrite: '+str(outfile))
 graph=load(BASE/'ref2va-audio-comparison-graph.json');w,h=internal_size(req['width'],req['height'])
 creative_start=not index and ref and bool(req.get('staged_references')) and req.get('reference_creativity',0)>0
 if index:
  action=shot.get('continuation_action') or 'Continue forward naturally from the current pose and situation, completing the scene without restarting earlier actions.'
  prompt=f"Continue seamlessly from the previous final frame. {action} Keep the same character, clothing and setting. Do not restart or repeat actions already completed. The character speaks the supplied recording naturally with precise lip movement."
 elif creative_start:
  prompt=f"{shot['character']} {shot['scene']} {shot['action']} {shot['prompt']} Visual style: {req['style']}. {character_reference_guidance(req['reference_creativity'])} The character speaks the supplied recording naturally with precise lip movement."
 elif ref:
  prompt=f"The same character from the reference image keeps the exact face, hair, clothing, colors and setting. {shot['action']} The character speaks the supplied recording naturally with precise lip movement. Preserve the original character and scene."
 else:
  prompt=f"{shot['character']} {shot['scene']} {shot['action']} {shot['prompt']} Visual style: {req['style']}. The character speaks the supplied recording naturally with precise lip movement. Preserve identity, clothing, and scene."
 graph['157']['inputs'].update(width=w,height=h,length=req.get('segment_frames',FRAMES),prompt=prompt)
 graph['142']['inputs'].update(width=w,height=h)
 if ref:
  ref=Path(ref);name=f"lf-{state['job_id']}-{key}{ref.suffix.lower()}";dest=BASE/'input'/name
  if not dest.exists():shutil.copyfile(ref,dest)
  graph['5']['inputs']['image']=name;graph['157']['inputs']['first_frame']=['142',0]
 else:graph['157']['inputs'].pop('first_frame',None)
 voice=Path(shot['voice']);audio_name=f"lf-{state['job_id']}-{shot['id']}.wav";audio_dest=BASE/'input'/audio_name
 if not audio_dest.exists():shutil.copyfile(voice,audio_dest)
 span=req.get('segment_frames',FRAMES)/FPS;overlap=req.get('continuation_overlap_frames',0)/FPS
 graph['18']['inputs']['audio']=audio_name;graph['19']['inputs']['start_seconds']=index*(span-overlap);graph['130']['inputs']['noise_seed']=int(req.get('seed',2801))+int(shot['id'][-2:])*100+index
 graph['136']['inputs']['filename_prefix']=f"local-film/{state['job_id']}/{key}"
 # Continuations use the distilled first-frame guide. Reference conditioning
 # alone does not anchor the tail frame and can restart the object's action.
 if not index and (req.get('staged_object_reference') or creative_start):
  if req.get('staged_object_reference'):
   obj=Path(req['staged_object_reference']['path']);name=f"lf-{state['job_id']}-object{obj.suffix.lower()}";dest=BASE/'input'/name
   if not dest.exists():shutil.copyfile(obj,dest)
   graph['161']={'class_type':'LoadImage','inputs':{'image':name}}
  char_image=['5',0] if creative_start else ['142',0]
  inputs={'clip':['13',0],'vae':['11',0],'audio_vae':['24',0],'width':w,'height':h,'length':req.get('segment_frames',FRAMES),'ref_image_size':'match','ref_images.ref_image_0':char_image if ref else ['161',0]}
  inputs['prompt']=prompt
  if creative_start:inputs['prompt']+=' Use <Picture 1> as the character reference according to the creative guidance above.'
  if req.get('staged_object_reference'):
   if ref:inputs['ref_images.ref_image_1']=['161',0]
   picture=2 if ref else 1;inputs['prompt']+=f" Use <Picture {picture}> as the visual reference for {req.get('object_description') or 'the object in the scene'}."
  graph['157']={'class_type':'MiniMaxH3ReferenceToVideo','inputs':inputs}
  graph['160']={'class_type':'SenseNovaH3DistilledBridge','inputs':{'conditioning':['157',0],'distilled_adapter':'MiniMaxH3_SemanticBridge_v1.safetensors','alpha':0.15,'magnitude_match':'per_token'}}
  graph['19']['inputs']['positive']=['160',0]
 if motion_ref:
  name=f"lf-{state['job_id']}-{key}-motion.mp4";dest=BASE/'input'/name
  if not dest.exists():shutil.copyfile(motion_ref,dest)
  graph['162']={'class_type':'VHS_LoadVideo','inputs':{'video':name,'force_rate':24,'custom_width':0,'custom_height':0,'frame_load_cap':req['continuation_overlap_frames'],'skip_first_frames':0,'select_every_nth':1,'format':'H3'}}
  graph['142']['inputs']['image']=['162',0];graph['157']['inputs'].pop('first_frame',None)
  graph['163']={'class_type':'MiniMaxH3AddGuide','inputs':{'positive':['157',0],'latent':['157',1],'vae':['11',0],'image':['142',0],'frame_idx':0}}
  graph['19']['inputs']['positive']=['163',0]
  graph['157']['inputs']['prompt']=graph['157']['inputs']['prompt'].replace('Continue seamlessly from the previous final frame.','Continue the existing motion from the supplied opening video guide.')
 if req.get('segment_instructions','').strip():
  graph['157']['inputs']['prompt']+='\nInstructions for every segment (take precedence over conflicting descriptions above):\n'+req['segment_instructions']
 if record is None:
  prompt_id=str(uuid.uuid4());record={'prompt_id':prompt_id,'status':'prepared','graph':graph,'attempt':1};state['segments'][key]=record;save(job,state)
 else:prompt_id=record['prompt_id'];graph=record['graph']
 if record['status']=='complete':raise JobError(f'Completed segment file is missing: {outfile}; restore it before resuming')
 if record['status'] in ('submitting','submitted'):
  state['status']='rendering';save(job,state)
  status,entry=locate(prompt_id)
  if status=='unknown':raise JobError(f'Unknown outcome for {key} ({prompt_id}); inspect ComfyUI history and outputs before retrying')
 else:
  wait_idle(state,job);record['status']='submitting';record['started']=time.time();state['status']='rendering';save(job,state)
  try:
   result=api('/prompt',{'prompt':graph,'prompt_id':prompt_id,'client_id':'local-film-'+state['job_id']});record['status']='submitted';save(job,state)
  except Exception:
   status,entry=locate(prompt_id)
   if status=='unknown':raise JobError(f'Submission outcome unknown for {key}; inspect ComfyUI before retrying')
  status,entry=locate(prompt_id)
 while status not in ('history','unknown'):
  time.sleep(10);check_cancel(job);status,entry=locate(prompt_id)
 if status=='unknown':raise JobError(f'ComfyUI lost job {prompt_id}; inspect outputs before retrying')
 if entry.get('status',{}).get('status_str')!='success':
  failure=str(entry.get('status',{}).get('messages',[]))
  if ('out of memory' in failure.lower() or 'outofmemory' in failure.lower()) and record.get('attempt',1)<2:
   old_w,old_h=graph['157']['inputs']['width'],graph['157']['inputs']['height'];new_w=max(32,(int(old_w*0.75)//32)*32);new_h=max(32,(int(old_h*0.75)//32)*32)
   graph['157']['inputs'].update(width=new_w,height=new_h);graph['142']['inputs'].update(width=new_w,height=new_h)
   try:api('/free',{'unload_models':True,'free_memory':True})
   except Exception:pass
   record.update(prompt_id=str(uuid.uuid4()),status='prepared',attempt=2,graph=graph,retry_reason='GPU out of memory; reduced internal generation size',previous_prompt_id=prompt_id)
   log(state,'oom_retry',segment=key,old_size=[old_w,old_h],new_size=[new_w,new_h]);save(job,state)
   return render_segment(job,state,shot,index,ref,req,motion_ref)
  raise JobError(f'Segment {key} failed: {failure[:1800]}')
 result=entry['outputs']['136']['gifs'][0];source=BASE/'output'/result['subfolder']/result['filename']
 if not source.is_file():raise JobError('ComfyUI reported success but output is missing: '+str(source))
 run_cmd(['ffmpeg','-v','error','-xerror','-i',source,'-map','0:v:0','-map','0:a:0','-f','null','-'])
 shutil.copy2(source,outfile);record.update(status='complete',completed=time.time(),output=str(outfile),elapsed_seconds=time.time()-record['started']);save(job,state)
 return outfile

def extract_tail(video,target):
 if target.exists():return target
 temp=target.with_name(target.stem+'.partial.png');run_cmd(['ffmpeg','-y','-v','error','-sseof','-0.042','-i',video,'-frames:v','1',temp]);os.replace(temp,target);return target

def extract_motion_tail(video,target,req):
 if target.exists():return target
 start=req.get('segment_frames',FRAMES)-req['continuation_overlap_frames'];temp=target.with_name(target.stem+'.partial.mp4')
 run_cmd(['ffmpeg','-y','-v','error','-i',video,'-vf',f'trim=start_frame={start},setpts=PTS-STARTPTS','-an','-c:v','libx264','-crf','0','-pix_fmt','yuv420p',temp]);os.replace(temp,target);return target

def trim_overlap(video,target,part):
 if target.exists():return target
 target.parent.mkdir(exist_ok=True);temp=target.with_name(target.stem+'.partial.mp4')
 run_cmd(['ffmpeg','-y','-v','error','-i',video,'-filter_complex',f"[0:v]trim=start={part['trim_start']:.9f}:duration={part['seconds']:.9f},setpts=PTS-STARTPTS[v];[0:a]atrim=start={part['trim_start']:.9f}:duration={part['seconds']:.9f},asetpts=PTS-STARTPTS[a]",'-map','[v]','-map','[a]','-c:v','libx264','-crf','16','-c:a','aac','-b:a','192k',temp]);os.replace(temp,target);return target

def assemble(job,plan,req,segments):
 output=job/'review'/'assembled.mp4';output.parent.mkdir(exist_ok=True)
 if output.exists():return output
 args=['ffmpeg','-y','-v','error'];filters=[];pieces=[]
 for i,(path,seconds) in enumerate(segments):
  args+=['-i',str(path)];filters += [f'[{i}:v]trim=duration={seconds:.6f},setpts=PTS-STARTPTS,scale={req["width"]}:{req["height"]}:force_original_aspect_ratio=increase,crop={req["width"]}:{req["height"]},setsar=1,fps={req["fps"]}[v{i}]',f'[{i}:a]atrim=duration={seconds:.6f},asetpts=PTS-STARTPTS,aresample=32000[a{i}]'];pieces += [f'[v{i}][a{i}]']
 filters.append(''.join(pieces)+f'concat=n={len(segments)}:v=1:a=1[v][voice]')
 if req.get('staged_music'):
  args+=['-stream_loop','-1','-i',req['staged_music']];filters.append(f'[{len(segments)}:a]volume=0.12,aresample=32000[music]');filters.append('[voice][music]amix=inputs=2:duration=first:dropout_transition=0[a]')
 else:filters.append('[voice]anull[a]')
 tmp=output.with_name('assembled.partial.mp4');args+=['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(tmp)];run_cmd(args);os.replace(tmp,output);return output

def audio_vector(path):
 from array import array
 raw=run_cmd(['ffmpeg','-v','error','-i',path,'-vn','-ac','1','-ar','8000','-f','f32le','-']).stdout
 result=array('f');result.frombytes(raw);return result

def correlation(a,b):
 n=min(len(a),len(b))
 if n<100:return None
 a=a[:n];b=b[:n];ma=sum(a)/n;mb=sum(b)/n
 cross=sum((x-ma)*(y-mb) for x,y in zip(a,b));aa=sum((x-ma)**2 for x in a);bb=sum((y-mb)**2 for y in b)
 return cross/math.sqrt(aa*bb) if aa>1e-12 and bb>1e-12 else None

def visual_stats(path,seconds=None):
 from array import array
 raw=run_cmd(['ffmpeg','-v','error','-i',path]+(['-t',str(seconds)] if seconds else [])+['-vf','fps=2,scale=90:160,format=gray','-f','rawvideo','-']).stdout;size=90*160;frames=[raw[i:i+size] for i in range(0,len(raw)-size+1,size)]
 changes=[sum(abs(a-b) for a,b in zip(x,y))/size for x,y in zip(frames,frames[1:])]
 first_changes=[sum(abs(a-b) for a,b in zip(frames[0],f))/size for f in frames[1:]] if frames else []
 return {'samples':len(frames),'mean_difference':round(sum(changes)/len(changes),3) if changes else 0,'max_difference':round(max(changes),3) if changes else 0,'max_change_from_first':round(max(first_changes),3) if first_changes else 0}

def continuity(previous,current):
 a=run_cmd(['ffmpeg','-v','error','-sseof','-0.042','-i',previous,'-frames:v','1','-vf','scale=90:160,format=gray','-f','rawvideo','-']).stdout
 b=run_cmd(['ffmpeg','-v','error','-i',current,'-frames:v','1','-vf','scale=90:160,format=gray','-f','rawvideo','-']).stdout
 if len(a)!=len(b) or not a:return None
 return round(sum(abs(x-y) for x,y in zip(a,b))/len(a),3)

def quality(job,plan,req,segments,output):
 flags=[];tests=[];infos=media(output);video=next((x for x in infos['streams'] if x['codec_type']=='video'),None);audio=next((x for x in infos['streams'] if x['codec_type']=='audio'),None);expected=sum(s for _,s in segments)
 if not video or (video['width'],video['height'])!=(req['width'],req['height']):flags.append('Wrong output video dimensions')
 if not audio:flags.append('Output audio stream missing')
 if float(infos['format']['duration'])+0.15<expected:flags.append('Assembled video appears truncated')
 run_cmd(['ffmpeg','-v','error','-xerror','-i',output,'-map','0:v:0','-map','0:a:0','-f','null','-'])
 assembled_audio=audio_vector(output);cursor=0;assembled_audio_checks=[]
 for shot in plan['shots']:
  source=audio_vector(Path(shot['voice']));part=assembled_audio[cursor:cursor+len(source)];score=correlation(source,part)
  assembled_audio_checks.append({'shot':shot['id'],'source_samples':len(source),'output_samples':len(part),'correlation':round(score,4) if score is not None else None})
  if len(part)+800<len(source) or score is None or score<0.75:flags.append(shot['id']+': assembled narration may be missing, truncated or out of sync')
  cursor+=round(shot['duration_seconds']*8000)
 segment_iter=iter(segments)
 for shot in plan['shots']:
  source=audio_vector(Path(shot['voice']));previous=None
  for part in segment_schedule(shot['duration_seconds'],req):
   path,seconds=next(segment_iter);samples=audio_vector(path)[:round(seconds*8000)];start=round(part['timeline_start']*8000);actual=source[start:start+len(samples)];corr=correlation(actual,samples);rms=math.sqrt(sum(x*x for x in samples)/max(1,len(samples)));motion=visual_stats(path,seconds)
   entry={'segment':path.name,'duration':duration(path),'audio_rms':round(rms,5),'source_audio_correlation':round(corr,4) if corr is not None else None,'motion':motion}
   if duration(path)+0.1<seconds:flags.append(path.name+': video shorter than expected')
   if len(actual)>8000 and (corr is None or corr<0.8):flags.append(path.name+': narration may be missing or out of sync')
   if motion['mean_difference']<0.8:flags.append(path.name+': sampled frames appear unusually static; review motion')
   if motion['max_change_from_first']>45:flags.append(path.name+': large visual change within shot; review character, clothing and scene consistency')
   if previous:
    diff=continuity(previous,path);entry['join_mean_difference']=diff
    if diff is None or diff>18:flags.append(path.name+': possible visual discontinuity at join')
   tests.append(entry);previous=path
 report={'output':str(output),'duration_seconds':duration(output),'dimensions':[video.get('width'),video.get('height')] if video else None,'checks':tests,'assembled_audio_checks':assembled_audio_checks,'flags':flags,'limitations':['Visual change and motion scores can be affected by camera moves and lighting.','Automated checks cannot judge acting, facial identity, phoneme-level lip sync, story quality, or music suitability. Human playback review is required.']}
 if req.get('staged_object_reference'):report['limitations'].append('Object-reference conditioning is experimental; inspect object fidelity and continuation joins.')
 atomic(job/'review'/'quality.json',report)
 lines=['# Local film quality report','',f"Output: {output.name}",f"Duration: {report['duration_seconds']:.2f} seconds",f"Resolution: {req['width']} x {req['height']}",'','## Flags']+[('- '+x) for x in flags or ['No automated flags; human review is still required.']]+['','## Assembled narration checks']+[f"- {t['shot']}: source correlation {t['correlation']}" for t in assembled_audio_checks]+['','## Segment checks']+[f"- {t['segment']}: audio correlation {t['source_audio_correlation']}, sampled motion {t['motion']['mean_difference']}, join difference {t.get('join_mean_difference', 'n/a')}" for t in tests]+['','## Limits']+['- '+x for x in report['limitations']]
 (job/'review'/'quality.md').write_text('\n'.join(lines)+'\n',encoding='utf8');return report

def run(job,plan_only=False,open_folder=True):
 job=Path(job).resolve()
 if not job.is_relative_to(JOBS.resolve()) or not (job/'state.json').is_file():raise JobError('Not a local film job directory')
 # All pipeline stages, not only GPU generation, are serialized across processes.
 with locked(JOBS/'pipeline.lock',wait=True):
  return _run_one(job,plan_only,open_folder)

def _run_one(job,plan_only,open_folder):
 with locked(job/'job.lock'):
  state=load(job/'state.json');req=validate(load(job/'request.json'))
  if state['status']=='complete':return state
  state.pop('error',None);save(job,state)
  try:
   check_cancel(job);plan=make_plan(job,state);check_cancel(job)
   shots=plan.get('shots')
   if not isinstance(shots,list) or not 1<=len(shots)<=12:raise JobError('Plan must contain 1 to 12 shots')
   ids=[]
   for shot in shots:
    if not isinstance(shot,dict) or not all(isinstance(shot.get(k),str) and shot[k].strip() for k in ('id','narration','character','scene','action','prompt')):raise JobError('Plan has missing shot fields')
    if not re.fullmatch(r'shot-[0-9]{2}',shot['id']):raise JobError('Plan shot ids must be shot-01 through shot-99')
    ids.append(shot['id'])
   if len(ids)!=len(set(ids)):raise JobError('Plan shot ids must be unique')
   if plan_only:state['status']='planned';save(job,state);return state
   state['status']='voicing';save(job,state);plan=voice(job,state,plan)
   check_cancel(job);ensure_server();segments=[];shared_ref=req['staged_references'][0]['path'] if req['staged_references'] else None
   with locked(JOBS/'gpu.lock',wait=True):
    for shot_index,shot in enumerate(plan['shots']):
     reference=(req['staged_references'][min(shot_index,len(req['staged_references'])-1)]['path'] if req['staged_references'] else shared_ref)
     motion_ref=None
     for part in segment_schedule(shot['duration_seconds'],req):
      i=part['index'];path=render_segment(job,state,shot,i,reference,req,motion_ref)
      if not shared_ref:
       shared_ref=job/'references'/'generated-first-frame.png';shared_ref.parent.mkdir(exist_ok=True)
       if not shared_ref.exists():run_cmd(['ffmpeg','-y','-v','error','-i',path,'-frames:v','1',shared_ref])
      reference=extract_tail(path,job/'references'/f"{shot['id']}-{i:02}-tail.png")
      if req.get('continuation_overlap_frames',0):motion_ref=extract_motion_tail(path,job/'references'/f"{shot['id']}-{i:02}-motion.mp4",req)
      aligned=trim_overlap(path,job/'segments-aligned'/path.name,part) if part['trim_start'] else path
      segments.append((aligned,part['seconds']))
   q=api('/queue')
   if not q.get('queue_running') and not q.get('queue_pending'):
    try:api('/free',{'unload_models':True,'free_memory':True})
    except Exception:pass
   check_cancel(job);state['status']='assembling';save(job,state);started=time.time();output=assemble(job,plan,req,segments);log(state,'assembled',seconds=round(time.time()-started,2))
   check_cancel(job);state['status']='checking';save(job,state);started=time.time();report=quality(job,plan,req,segments,output);log(state,'quality_checked',seconds=round(time.time()-started,2))
   review=job/'review';shutil.copy2(job/'plan.json',review/'shot-plan.json');shutil.copy2(job/'request.json',review/'settings.json')
   segdir=review/'segments';segdir.mkdir(exist_ok=True)
   for p,_ in segments:
    if not (segdir/p.name).exists():shutil.copy2(p,segdir/p.name)
   previews=review/'previews';previews.mkdir(exist_ok=True)
   for p,_ in segments:
    target=previews/(p.stem+'-contact.jpg')
    if not target.exists():run_cmd(['ffmpeg','-y','-v','error','-i',p,'-vf','fps=2,scale=180:-1,tile=4x3','-frames:v','1',target])
   atomic(review/'prompts.json',{k:v['graph']['157']['inputs']['prompt'] for k,v in state['segments'].items()})
   check_cancel(job);state['status']='complete';state['completed']=time.time();state['output']=str(output);state['quality_flags']=report['flags'];save(job,state);shutil.copy2(job/'state.json',review/'generation-state.json')
   if open_folder and os.name=='nt':
    try:subprocess.Popen(['explorer.exe',str(review)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except OSError as e:
     state['folder_open_warning']=str(e);save(job,state);atomic(review/'generation-state.json',state)
   return state
  except Exception as e:
   state['status']='failed';state['error']=str(e);log(state,'failed',error=str(e));save(job,state);raise

def main():
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='cmd',required=True)
 new=sub.add_parser('create');new.add_argument('request',type=Path)
 for name in ['run','plan']:
  p=sub.add_parser(name);p.add_argument('job',type=Path);p.add_argument('--no-open',action='store_true')
 args=parser.parse_args()
 if args.cmd=='create':print(create(load(args.request)))
 else:print(json.dumps(run(args.job,plan_only=args.cmd=='plan',open_folder=not args.no_open),indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print('Local film error: '+str(e),file=sys.stderr);sys.exit(1)
