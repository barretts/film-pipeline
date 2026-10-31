"""Directing layer: stateful beats with deliberate cuts, bounded gates and an event ledger.

Behaviour lifted from the accepted story experiments (jobs/story-progress-smoke,
story-cut-smoke, story-next-scene) and isolated from the episode batch path: nothing in
local_film.pipeline or local_film.series depends on this module. GPU endpoints are only
touched when run_directive(mode='managed'); the default dry mode validates and builds
graphs on CPU without contacting ComfyUI."""
import contextlib,copy,hashlib,json,shutil,subprocess,sys,time,uuid
from pathlib import Path
from . import pipeline as P, series as S, characters as C

GONE_PREFIXES=('missing','dead','departed')
REQUIRED_NODES=('5','18','19','130','136','157')

class DirectiveError(RuntimeError):pass

def is_gone(value):return str(value).lower().startswith(GONE_PREFIXES)

def sha256(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
 return h.hexdigest()

def normalize_plan(plan):
 """Accept experiment plans (cut_to_new_location booleans, reused_exit/approved_cut) and canonicalize."""
 plan=copy.deepcopy(plan)
 plan.setdefault('schema',1)
 plan.setdefault('id',str(plan.get('experiment','directive')))
 plan.setdefault('initial_state',{})
 plan.setdefault('max_changed_retries',1)
 plan.setdefault('review_timeout_s',300)
 plan.setdefault('gpu','managed')
 plan.setdefault('template_segment','shot-01-01')
 if 'seed' not in plan:
  plan['seed']=plan.get('generation',{}).get('seed',13)
 plan.setdefault('first_guide',None)
 if 'prefix_clips' not in plan:
  clips=[];legacy=False
  if plan.get('approved_cut'):clips.append(plan['approved_cut']);legacy=True
  elif plan.get('source_job') and plan.get('preserve_opening'):
   clips+= [str(Path(plan['source_job'])/'segments'/(name+'.mp4')) for name in plan['preserve_opening']]
   if plan.get('reused_exit'):clips.append(plan['reused_exit']);legacy=True
  plan['prefix_clips']=clips
  beats=plan.get('beats') or []
  if legacy and beats and plan.get('initial_state') and beats[0].get('before') and beats[0]['before']!=plan['initial_state']:
   # The declared initial_state is true at the start of the preserved prefix; the story
   # events inside the already-approved prefix leave the ledger at the first beat's before state.
   plan['prefix_declared_state']=plan['initial_state']
   plan['initial_state']=beats[0]['before']
   plan['state_note']='initial_state moved to the end of the approved prefix; see prefix_declared_state'
 for beat in plan.get('beats',[]):
  if 'cut' not in beat:beat['cut']='new_location' if beat.get('cut_to_new_location') else 'continuation'
  beat.setdefault('re_entry_cast',[])
  beat.setdefault('first_guide',None)
  beat.setdefault('cast_at_end',None)
 return plan

def validate(plan,cast_slugs):
 """Raise DirectiveError unless every beat is renderable against the committed story state."""
 beats=plan.get('beats') or []
 if not beats:raise DirectiveError('directive has no beats')
 if plan.get('max_changed_retries') not in (0,1):raise DirectiveError('max_changed_retries must be 0 or 1')
 if plan.get('gpu') not in ('off','managed'):raise DirectiveError("gpu must be 'off' or 'managed'")
 state=dict(plan.get('initial_state') or {})
 if not state:raise DirectiveError('initial_state is required')
 seen=set()
 for beat in beats:
  bid=str(beat.get('id') or '')
  if not bid:raise DirectiveError('every beat needs an id')
  if bid in seen:raise DirectiveError('duplicate beat id: '+bid)
  seen.add(bid)
  for key in ('before','after'):
   value=beat.get(key)
   if not isinstance(value,dict) or not value:raise DirectiveError(f'{bid}: {key} must be a non-empty state map')
   if any(not isinstance(v,str) or not v for v in value.values()):raise DirectiveError(f'{bid}: {key} values must be non-empty strings')
  if not str(beat.get('action','')).strip():raise DirectiveError(f'{bid}: one achievable action is required')
  if beat.get('cut') not in ('continuation','new_location'):raise DirectiveError(f'{bid}: cut must be continuation or new_location')
  cast=beat.get('on_screen_cast') or []
  if not cast:raise DirectiveError(f'{bid}: explicit on_screen_cast is required')
  if len(set(cast))!=len(cast):raise DirectiveError(f'{bid}: duplicate slugs in on_screen_cast')
  unknown=[slug for slug in cast if slug not in cast_slugs]
  if unknown:raise DirectiveError(f'{bid}: unknown cast: '+', '.join(unknown))
  acceptance=beat.get('acceptance') or []
  if not isinstance(acceptance,list) or not acceptance or any(not str(x).strip() for x in acceptance):raise DirectiveError(f'{bid}: non-empty acceptance list is required')
  dialogue=beat.get('dialogue') or []
  audio=beat.get('audio')
  if dialogue:
   if audio=='silence' or not audio:raise DirectiveError(f'{bid}: spoken dialogue needs a timed audio recording, not silence')
   for line in dialogue:
    if line.get('character') not in cast_slugs:raise DirectiveError(f'{bid}: dialogue character not in show cast: '+str(line.get('character')))
    if not str(line.get('text','')).strip():raise DirectiveError(f'{bid}: dialogue line without text')
  elif audio!='silence':raise DirectiveError(f'{bid}: silent beats must declare audio="silence"')
  reentry=beat.get('re_entry_cast') or []
  if len(set(reentry))!=len(reentry):raise DirectiveError(f'{bid}: duplicate slugs in re_entry_cast')
  for slug in reentry:
   if slug not in cast:raise DirectiveError(f'{bid}: re_entry_cast {slug} is not on screen in this beat')
   if not is_gone(beat['before'].get(slug,'')):raise DirectiveError(f'{bid}: re_entry_cast {slug} is not departed in the before state')
   if is_gone(beat['after'].get(slug,'')):raise DirectiveError(f'{bid}: re_entry_cast {slug} must end present in the after state')
  if beat['before']!=state:raise DirectiveError(f'{bid}: before state must equal the committed story state; expected '+json.dumps(state,sort_keys=True)+' found '+json.dumps(beat['before'],sort_keys=True))
  # Departure integrity: ANY gone-to-present actor transition requires an explicit re-entry
  # beat (an off-screen reappearance is just as unauthorized as an on-screen one), departed
  # characters keep their established state key, and off-screen exits are not renderable.
  for slug,value in state.items():
   if slug not in cast_slugs:continue
   if slug not in beat['after']:raise DirectiveError(f'{bid}: {slug} dropped out of the after state map; established cast states must be preserved')
   if beat['after'][slug]!=value and slug not in beat['on_screen_cast']:raise DirectiveError(f'{bid}: off-screen {slug} cannot change state ({value!r} to {beat["after"][slug]!r}); only on-screen action may change an actor state')
   if is_gone(value) and not is_gone(beat['after'][slug]) and slug not in reentry:raise DirectiveError(f'{bid}: {slug} cannot go from departed to present without an explicit re_entry_cast beat, even off screen')
  for slug in cast:
   if slug in reentry:continue
   if slug in beat['before'] and is_gone(beat['before'][slug]):raise DirectiveError(f'{bid}: departed {slug} cannot be on screen without an explicit re_entry_cast beat')
  state=dict(beat['after'])

class StoryLedger:
 """Append-only take ledger; story state advances only on approved takes."""
 def __init__(self,initial_state,entries=None):
  self.initial_state=dict(initial_state);self.entries=list(entries or [])
 @property
 def state(self):
  state=dict(self.initial_state)
  for entry in self.entries:
   if entry.get('decision')=='approve':state.update(entry.get('after') or {})
  return state
 @property
 def departed(self):return {slug for slug,value in self.state.items() if is_gone(value)}
 def last_entry(self,beat_id):
  for entry in reversed(self.entries):
   if entry.get('beat')==beat_id:return entry
  return None
 def retries_used(self,beat_id):return sum(1 for entry in self.entries if entry.get('beat')==beat_id and entry.get('decision')=='retry')
 @classmethod
 def load(cls,path,initial_state):
  path=Path(path)
  data=P.load(path) if path.exists() else {'initial_state':dict(initial_state),'entries':[]}
  if data.get('initial_state') and dict(initial_state)!=data['initial_state']:raise DirectiveError(f'ledger {path} was started with a different initial_state; use a new job directory')
  return cls(data.get('initial_state') or dict(initial_state),data.get('entries') or [])
 def append(self,entry,path):
  self.entries.append(entry);P.atomic(Path(path),{'initial_state':self.initial_state,'entries':self.entries})

def compose_prompt(beat,show,cast,slugs,correction=''):
 detail=(str(show['style'])+'\n\nStarting story situation: '+json.dumps(beat['before'])
  +'\nOne continuous shot. '+str(beat['action']).strip()+'\nRequired ending situation: '+json.dumps(beat['after'])
  +'\nPreserve faces and clothing, while allowing the specified movement and departure. The action happens once and completes within this clip. No reset to an earlier event. ')
 if beat.get('dialogue'):detail+=' '.join(S._dialogue({'dialogue':beat['dialogue']},cast))+' Match only the supplied audio; do not repeat the line.'
 else:detail+='Silent physical action. Closed mouths, no dialogue, no speech or mimed conversation.'
 if correction:detail+='\nCorrection based on prior failed take: '+correction
 return S._six_sections(show,cast,slugs,detail)

def build_graph(template,beat,cast,show,slugs,guide_name,audio_name,seed,take_name,output_prefix,correction=''):
 for node in REQUIRED_NODES:
  if node not in template:raise DirectiveError('template graph is missing node '+node)
 graph=copy.deepcopy(template);inputs=graph['157']['inputs']
 for key in [k for k in list(inputs) if k.startswith('ref_images.')]:del inputs[key]
 for offset in range(16):
  node=str(170+offset)
  if node in graph:graph.pop(node,None)
 for slot,slug in enumerate(slugs):
  graph[str(170+slot)]={'class_type':'LoadImage','inputs':{'image':f'{take_name}-{slug}.png'}}
  inputs[f'ref_images.ref_image_{slot}']=[str(170+slot),0]
 inputs['prompt']=compose_prompt(beat,show,cast,slugs,correction)
 inputs['length']=P.FRAMES
 graph['5']['inputs']['image']=guide_name
 if beat['cut']=='new_location':
  graph.pop('163',None);graph['19']['inputs']['positive']=['160',0]
 graph['18']['inputs']['audio']=audio_name
 graph['19']['inputs']['start_seconds']=0
 graph['130']['inputs']['noise_seed']=int(seed)
 graph['136']['inputs']['filename_prefix']=output_prefix
 return graph

def best_correlation(source,mix,max_lag_seconds=0.001,sample_rate=8000):
 """Correlation with a +/-1 ms lag search; returns (score, lag_samples)."""
 max_lag=max(1,int(round(sample_rate*max_lag_seconds)));best=None
 for lag in range(-max_lag,max_lag+1):
  if lag>=0:score=P.correlation(source,list(mix)[lag:] or [0.0])
  else:score=P.correlation(list(source)[-lag:] or [0.0],mix)
  if score is not None and (best is None or score>best[0]):best=(score,lag)
 return best or (None,0)

def silence_wav(path,seconds):
 path=Path(path)
 if path.exists():return path
 P.run_cmd(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'anullsrc=r=22050:cl=mono','-t',str(seconds),path])
 return path

def review_gate(decision_path,timeout_s=300,clock=time.monotonic,sleep=time.sleep):
 path=Path(decision_path);deadline=clock()+timeout_s
 while not path.exists():
  if clock()>deadline:raise DirectiveError(f'Review timeout after {timeout_s}s awaiting {path}')
  sleep(2)
 decision=P.load(path)
 if decision.get('decision') not in ('approve','retry','reject'):raise DirectiveError('review decision must be approve, retry or reject: '+str(path))
 if decision['decision']=='retry' and not str(decision.get('correction','')).strip():raise DirectiveError('retry requires a documented correction; blind retries are not allowed')
 return decision

def audit_take(video,beat,job,dialogue_wav=None,run=None):
 """CPU audits: full decode, tail frame, 6-frame sheet, 16-frame grid; correlation for spoken beats."""
 run=run or P.run_cmd
 video=Path(video);name=video.name.rsplit('.',1)[0];out={}
 run(['ffmpeg','-v','error','-xerror','-i',video,'-map','0:v:0','-map','0:a:0','-f','null','-'])
 tail=job/(name+'-tail.png');P.extract_tail(video,tail);out['tail']=str(tail)
 sheet=job/(name+'-audit-sheet.jpg')
 run([sys.executable,P.ROOT/'tools/contact_sheet.py','--videos',video,'--frames','0,0.2,0.4,0.6,0.8,0.99','--out',sheet,'--title',name])
 out['sheet']=str(sheet)
 grid=job/(name+'-audit-16.jpg')
 run(['ffmpeg','-y','-v','error','-i',video,'-vf',"select='not(mod(n\\,7))',scale=320:-1,tile=4x4",'-frames:v','1','-update','1',str(grid)])
 out['grid_16']=str(grid)
 if dialogue_wav:
  source=P.audio_vector(dialogue_wav);mix=P.audio_vector(video)
  score,lag=best_correlation(source,mix)
  out['audio']={'source_seconds':round(len(source)/8000,6) if source else 0,'correlation':round(score,5) if score is not None else None,'lag_samples':lag}
 P.atomic(job/(name+'-audit.json'),{'take':name,'acceptance':list(beat['acceptance']),'machine_results':out})
 return out

def _guide_source(plan,beat,guide):
 value=beat.get('first_guide') or guide or plan.get('first_guide')
 return Path(value) if value else None

def _audio_source(plan,beat):
 return None if beat.get('audio')=='silence' else Path(beat['audio'])

def plan_take(plan,beat,show,cast,state,guide,attempt,correction=''):
 """CPU-only take plan: graph + intended inputs, nothing staged and no GPU endpoints."""
 name=f"{plan['id']}-{beat['id']}-take{attempt}"
 slugs=[slug for slug in show['characters'] if slug in beat['on_screen_cast']]
 if beat['before']!=state:raise DirectiveError(f"{beat['id']}: before state no longer matches the committed story state")
 guide_src=_guide_source(plan,beat,guide);audio_src=_audio_source(plan,beat)
 graph=build_graph(plan['_template'],beat,cast,show,slugs,
  guide_src.name if guide_src else name+'-pending-guide.png',
  audio_src.name if audio_src else name+'-silence.wav',
  plan['seed'],name,f"{plan['id']}/{name}",correction)
 return {'beat':beat['id'],'take':attempt,'status':'planned','take_name':name,'graph':graph,
  'guide':str(guide_src) if guide_src else None,'guide_pending':guide_src is None or not guide_src.is_file(),
  'audio':str(audio_src) if audio_src else 'silence','dialogue_wav':str(audio_src) if audio_src else None,
  'on_screen_cast':list(beat['on_screen_cast']),'cut':beat['cut'],'correction':correction}

def _powershell(*args):return ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass']+list(args)

_UNSET=object()
@contextlib.contextmanager
def gpu_session(api=None,run=None,log=print,log_dir=None,sleep=_UNSET):
 """Own the GPU for one managed directive session with the project locks; Strata is stopped
 for the render window and restoration is guaranteed (and verified) on every exit path,
 including success, rejection, exception and timeout. Mirrors the accepted experiment runs."""
 api=api or P.api
 run=run or subprocess.run
 sleep=time.sleep if sleep is _UNSET else sleep
 with P.locked(P.JOBS/'pipeline.lock'),P.locked(P.JOBS/'gpu.lock'):
  queue=api('/queue')
  if queue.get('queue_running') or queue.get('queue_pending'):raise DirectiveError('GPU queue occupied; refusing to take ownership while renders are queued')
  log('Stopping Strata for the bounded directive session')
  try:
   run(_powershell('-File',str(P.ROOT/'jobs'/'orbit-smoke'/'kill-strata.ps1')),check=True)
   request=P.urllib.request.Request(P.ADDR+'/free',data=json.dumps({'unload_models':True,'free_memory':True}).encode(),headers={'Content-Type':'application/json'})
   with P.OPENER.open(request,timeout=30) as response:response.read()
   sleep(5)
   yield
  finally:
   # The render process may have died (exception, timeout, interrupt); Strata must come back no matter what.
   log('Restoring Strata after directive session')
   restore_log=(Path(log_dir)/'gpu-restore.log').open('w',encoding='utf8') if log_dir else contextlib.nullcontext()
   with restore_log as handle:
    restore=run(_powershell('-File',str(P.ROOT/'jobs'/'orbit-smoke'/'run.ps1'),'-RestoreOnly'),
     **({'stdout':handle,'stderr':subprocess.STDOUT} if handle is not None else {}))
   code=getattr(restore,'returncode',0)
   if isinstance(code,int) and code!=0:raise DirectiveError('Strata restoration failed with exit '+str(code)+'; see '+str(Path(log_dir or '.')/'gpu-restore.log'))
   if log_dir:P.atomic(Path(log_dir)/'gpu-lifecycle.json',{'strata_restored':True,'restore_exit':code if isinstance(code,int) else None,'restored_at':time.strftime('%Y-%m-%d %H:%M:%S')})

def submit_take(plan,record,show,cast,job,api=None,locate=None,clock=time.monotonic,sleep=time.sleep,timeout_s=720):
 """Managed-mode submission mirroring the experiment runners; every GPU touch is guarded."""
 api=api or P.api;locate=locate or P.locate
 name=record['take_name'];take_file=job/(name+'.json');output=job/(name+'.mp4')
 if output.exists():raise DirectiveError('Existing take must be reviewed, not overwritten: '+str(output))
 graph=copy.deepcopy(record['graph'])
 # A prior submission must be reconciled from its persisted record and prompt history,
 # never overwritten with a fresh UUID: the first outcome may simply be unknown to us.
 prior=P.load(take_file) if take_file.exists() else None
 if prior and prior.get('status')=='planned':prior=None
 prompt_id=prior.get('prompt_id') if prior else None
 if prior and not prompt_id:raise DirectiveError(f"{name}: take record claims {prior.get('status')} without a prompt_id; refusing to resubmit an outcome we cannot verify")
 # Stage inputs into the ComfyUI input directory under the graph-referenced names.
 def stage(src,target_name):
  if not Path(src).is_file():raise DirectiveError('missing input for '+target_name+': '+str(src))
  shutil.copy2(src,P.BASE/'input'/target_name)
 if prompt_id:
  record.update(prompt_id=prompt_id,status='reconciling',guide=prior.get('guide',record.get('guide')));P.atomic(take_file,record)
 else:
  queue=api('/queue')
  if queue.get('queue_running') or queue.get('queue_pending'):raise DirectiveError('GPU queue occupied; refusing concurrent render')
  guide=record['guide']
  if guide:stage(guide,graph['5']['inputs']['image'])
  elif record.get('guide_pending'):raise DirectiveError('no guide frame available for '+name)
  slugs=[slug for slug in show['characters'] if slug in record['on_screen_cast']]
  for slot,slug in enumerate(slugs):
   character=cast[slug]
   stage(Path(character['_dir'])/character['portrait'],graph[str(170+slot)]['inputs']['image'])
  audio_ref=graph['18']['inputs']['audio']
  if record['audio']=='silence':silence_wav(P.BASE/'input'/audio_ref,P.FRAMES/P.FPS)
  else:stage(record['audio'],audio_ref)
  prompt_id=str(uuid.uuid4());record.update(prompt_id=prompt_id,status='submitting');P.atomic(take_file,record)
  api('/prompt',{'prompt':graph,'prompt_id':prompt_id,'client_id':'directing-layer'})
  record['status']='submitted';P.atomic(take_file,record)
 deadline=clock()+timeout_s
 while clock()<deadline:
  status,entry=locate(prompt_id)
  if status=='history':break
  if status=='unknown':raise DirectiveError('Ambiguous render outcome; inspect queue/history before any retry')
  sleep(10)
 else:
  queue=api('/queue')
  if any(row[1]==prompt_id for row in queue.get('queue_running',[])):api('/interrupt',{})
  raise DirectiveError(f'Render timed out after {timeout_s} seconds; interrupted only our own prompt')
 if entry.get('status',{}).get('status_str')!='success':
  record['status']='failed';P.atomic(take_file,{k:v for k,v in record.items() if k!='graph'})
  raise DirectiveError('Render failed: '+str(entry.get('status')))
 outputs=[P.BASE/'output'/str(item.get('subfolder',''))/item['filename'] for values in entry.get('outputs',{}).values() for key in ('gifs','videos') for item in values.get(key,[]) if str(item.get('filename','')).endswith('.mp4')]
 if not outputs:raise DirectiveError('No MP4 in output')
 try:shutil.copy2(outputs[0],output)
 except OSError as error:raise DirectiveError(f'{name}: history claims {outputs[0].name} but it cannot be copied ({error}); refusing to invent a result') from error
 record['output']=str(output);record['status']='complete';P.atomic(take_file,{k:v for k,v in record.items() if k!='graph'})
 return record

def run_directive(plan_path,job,mode='dry',show_root=None,show_name=None,render=None,gate=None,assemble=None,api=None,locate=None,log=print):
 """Validate, build and (in managed mode) render approved beats; dry mode performs zero GPU calls."""
 job=Path(job)
 plan=normalize_plan(P.load(Path(plan_path)))
 show_root=Path(show_root) if show_root else P.ROOT/'series'
 show_name=show_name or plan.get('show')
 if not show_name and plan.get('source_job'):
  try:show_name=Path(P.load(Path(plan['source_job'])/'request.json')['show_path']).name
  except Exception:pass
 if not show_name:raise DirectiveError("plan needs 'show' or a source_job request.json with show_path")
 show=C.load_show(show_root,show_name)
 cast=C.load_cast(show_root,show)
 validate(plan,set(cast))
 template=P.load(Path(plan['source_job'])/'state.json')['segments'][plan['template_segment']]['graph']
 plan['_template']=template
 ledger=StoryLedger.load(job/'story_state.json',plan.get('initial_state') or {})
 if ledger.entries:log('ledger resumed with '+str(len(ledger.entries))+' entries')
 if mode not in ('dry','managed'):raise DirectiveError("mode must be 'dry' or 'managed'")
 plan_records=[]
 if mode=='dry':
  state=dict(ledger.state);guide=plan.get('first_guide')
  for beat in plan['beats']:
   record=plan_take(plan,beat,show,cast,state,guide,1)
   P.atomic(job/(record['take_name']+'.json'),record);plan_records.append(record)
   state=dict(beat['after']);guide=str(Path(record['take_name']).with_suffix('.png'))
  P.atomic(job/'directive-plan.json',{'status':'planned','mode':'dry','takes':[record['take_name'] for record in plan_records],
   'guide_pending':[record['take_name'] for record in plan_records if record['guide_pending']],
   'projected_state_after':state,'commitments':{'ledger':'unchanged','gpu':'zero calls','media':'nothing staged or overwritten'}})
  log('directive planned on CPU: '+str(job/'directive-plan.json')+'; no GPU endpoints contacted')
  return {'planned':[record['take_name'] for record in plan_records]}
 with gpu_session(api=api,log=log,log_dir=job):
  render=render or (lambda record:submit_take(plan,record,show,cast,job,api=api,locate=locate))
  gate=gate or (lambda beat,record:review_gate(job/f"review-{record['take_name']}.json",plan['review_timeout_s']))
  budget=plan['max_changed_retries']
  # Resume support: replay beats already approved in the ledger, restoring their outputs,
  # the chained guide and per-beat retry usage; stop at the first beat still needing a take.
  guide=plan.get('first_guide');approved=[];start=0
  for index,beat in enumerate(plan['beats']):
   last=ledger.last_entry(beat['id'])
   if not last:break
   if last['decision']=='approve':
    expected=f"{plan['id']}-{beat['id']}-take{last.get('take')}"
    output=Path(last['output']) if last.get('output') else None
    tail=Path(last['tail']) if last.get('tail') else None
    if last.get('take_name')!=expected or last.get('after')!=beat['after']:raise DirectiveError(f"{beat['id']}: ledger approval does not match this plan revision ({expected}); use a new job directory")
    if not output or not tail or not output.is_file() or not tail.is_file() or output.name!=expected+'.mp4' or output.parent!=job:raise DirectiveError(f"{beat['id']}: approved take files are missing or outside this job ({output}, {tail}); restore them or use a new job directory")
    approved.append({'beat':beat['id'],'take':last['take'],'take_name':expected,'output':str(output)})
    guide=str(tail);start=index+1;continue
   if last['decision']=='reject':raise DirectiveError(f"{beat['id']}: take {last.get('take')} was rejected ({last.get('reason','no reason recorded')}); rejected takes are never overwritten and downstream beats stay stopped")
   break
  if start:log('resuming at beat '+plan['beats'][start]['id'] if start<len(plan['beats']) else 'all beats approved; finalizing only')
  for beat in plan['beats'][start:]:
   last=ledger.last_entry(beat['id'])
   if last and last['decision']=='retry':attempt=ledger.retries_used(beat['id'])+1;correction=str(last.get('correction','')).strip()
   else:attempt=1;correction=''
   if attempt-1>budget:raise DirectiveError(f"{beat['id']}: persisted retries ({attempt-1}) already exceed max_changed_retries={budget}")
   while True:
    record=plan_take(plan,beat,show,cast,ledger.state,guide,attempt,correction)
    record=render(record)
    if 'output' not in record:raise DirectiveError(f"{record['take_name']}: renderer produced no output")
    audit=audit_take(record['output'],beat,job,record.get('dialogue_wav'))
    record['audit']=audit;P.atomic(job/(record['take_name']+'.json'),{k:v for k,v in record.items() if k!='graph'})
    decision=gate(beat,record)
    if decision['decision']=='approve':
     ledger.append({'beat':beat['id'],'take':attempt,'take_name':record['take_name'],'decision':'approve','after':beat['after'],'output':record['output'],'tail':audit.get('tail'),'correlation':(audit.get('audio') or {}).get('correlation'),'cast_at_end':beat.get('cast_at_end') or beat['on_screen_cast'],'evidence':decision.get('evidence') or []},job/'story_state.json')
     guide=audit['tail'];approved.append(record);break
    if decision['decision']=='retry':
     if attempt-1>=budget:
      ledger.append({'beat':beat['id'],'take':attempt,'decision':'reject','reason':(str(decision.get('reason','')).strip() or 'review requested another retry')+'; changed-retry budget exhausted'},job/'story_state.json')
      raise DirectiveError(f"story acceptance failed at {beat['id']}: changed-retry budget exhausted ({budget}); downstream beats were not rendered")
     attempt+=1;correction=str(decision['correction']).strip()
     ledger.append({'beat':beat['id'],'take':attempt-1,'decision':'retry','correction':correction,'reason':decision.get('reason','')},job/'story_state.json');continue
    ledger.append({'beat':beat['id'],'take':attempt,'decision':'reject','reason':decision.get('reason',decision['decision'])},job/'story_state.json')
    raise DirectiveError(f"story acceptance failed at {beat['id']}: {decision.get('reason','review rejected')}; downstream beats were not rendered")
  paths=[Path(path) for path in plan['prefix_clips']]+[Path(record['output']) for record in approved]
  req=P.load(Path(plan['source_job'])/'request.json');req.pop('staged_music',None)
  segments=[(path,P.duration(path)) for path in paths]
  output=(assemble or (lambda job,segments:P.assemble(job,{},req,segments)))(job,segments)
  inputs={'plan.json':sha256(plan_path)}
  for path in paths:inputs[path.name]=sha256(path)
  P.atomic(job/'result.json',{'status':'awaiting_owner_playback','output':str(output),'inputs_sha256':inputs,
   'beats':[{'beat':entry['beat'],'take':entry['take'],'correlation':entry.get('correlation')} for entry in ledger.entries if entry.get('decision')=='approve'],
   'limitations':['Sampled audits are not an every-frame guarantee.','Perceived identity, lip sync and edit rhythm await owner playback.','Owner decision files are the visual gate; machine audits are advisory.']})
  log('directive assembled: '+str(output))
  return {'output':str(output),'approved':[record['take_name'] for record in approved]}
