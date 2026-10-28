"""Persistent FIFO dispatcher for local film jobs."""
import contextlib,threading,time,subprocess,sys,json,urllib.request
from pathlib import Path
from .pipeline import JOBS,ROOT,atomic,load,locked,JobError,api,OPENER,ADDR

ACTIVE={'starting','planning','voicing','waiting_for_gpu','rendering','assembling','checking','waiting_for_turn'}
TERMINAL={'complete','failed','planned','cancelled'}

class FilmQueue:
 def __init__(self,root=JOBS,spawn=None):
  self.root=Path(root);self.spawn=spawn or self._spawn;self.mutex=threading.RLock();self.worker=None;self.worker_job=None;self.wake=threading.Event()
 @contextlib.contextmanager
 def guard(self):
  with self.mutex:
   with locked(self.root/'queue-state.lock',wait=True):yield
 def _spawn(self,job,mode):
  log=(job/'worker.log').open('ab')
  try:return subprocess.Popen([sys.executable,'-m','local_film.pipeline',mode,str(job)],cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  finally:log.close()
 def scan(self):
  jobs=[]
  for path in self.root.glob('*/state.json'):
   try:
    state=load(path);jobs.append((path.parent,state))
   except (OSError,ValueError):continue
  return sorted(jobs,key=lambda x:(x[1].get('queued_at',x[1].get('created',0)),x[0].name))
 def _owns_job(self,job):
  try:
   with locked(job/'job.lock'):return False
  except (JobError,OSError):return True
 def enqueue(self,job,mode):
  if mode not in ('run','plan'):raise JobError('Invalid job mode')
  with self.guard():
   state=load(job/'state.json');status=state.get('status')
   if status=='complete':return state
   if status not in ('created','planned','failed','cancelled'):raise JobError('Job is already active or queued')
   if status=='cancelled':raise JobError('Cancelled jobs cannot be resumed; create a new job')
   state.update(status='queued',requested_mode=mode,queued_at=time.time(),queue_attempts=0);state.pop('error',None);atomic(job/'state.json',state)
  self.wake.set();return state
 def cancel(self,job):
  with self.guard():
   state=load(job/'state.json')
   if state.get('status')=='queued':
    state.update(status='cancelled',cancelled=time.time(),cancel_reason='Cancelled by user before dispatch');atomic(job/'state.json',state)
   elif state.get('status') in ACTIVE:
    atomic(job/'cancel-request.json',{'requested':time.time()});state=dict(state,status='cancelling')
   elif (job/'cancel-request.json').exists():state=dict(state,status='cancelling')
   else:raise JobError('Job has already finished or cannot be cancelled')
  self.wake.set();return state
 def list(self):
  with self.guard():
   jobs=self.scan();pending=[(j,s) for j,s in jobs if s.get('status')=='queued'];positions={j.name:i+1 for i,(j,_) in enumerate(pending)};result=[]
   for job,state in jobs:
    if state.get('status') not in ACTIVE|{'created','queued','failed','planned','cancelled','complete'}:continue
    display='cancelling' if (job/'cancel-request.json').exists() and state.get('status')!='cancelled' else state.get('status')
    result.append({'job_id':job.name,'status':display,'position':positions.get(job.name),'created':state.get('created'),'error':state.get('error')})
   return result
 def _comfy_post(self,path,payload):
  req=urllib.request.Request(ADDR+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with OPENER.open(req,timeout=30) as response:response.read()
 def tick(self):
  with self.guard():
   for job,state in self.scan():
    marker=job/'cancel-request.json'
    if not marker.exists():continue
    try:
     submitted=any(v.get('status') in ('submitting','submitted') for v in state.get('segments',{}).values())
     q=api('/queue') if submitted else {};owned=lambda item:len(item)>3 and item[3].get('client_id')=='local-film-'+job.name
     for item in q.get('queue_running',[]):
      if owned(item):self._comfy_post('/interrupt',{'prompt_id':item[1]})
     pending=[item[1] for item in q.get('queue_pending',[]) if owned(item)]
     if pending:self._comfy_post('/queue',{'delete':pending})
     if any(owned(item) for item in q.get('queue_running',[])+q.get('queue_pending',[])) or self._owns_job(job):return
     if self.worker_job==job and self.worker is not None and self.worker.poll() is None:return
     if state.get('status')=='starting' and time.time()-state.get('dispatch_started',0)<30:return
    except Exception as e:
     # Unknown ComfyUI state must not permit the next GPU job to start.
     print('Cancellation waiting:',str(e),flush=True);return
    state=load(job/'state.json')
    if state.get('status')!='complete':
     state.update(status='cancelled',cancelled=time.time(),cancel_reason='Cancelled by user while running');state.pop('error',None);atomic(job/'state.json',state)
    marker.unlink(missing_ok=True)
   if self.worker is not None:
    if self.worker.poll() is None:return
    self.worker=None;self.worker_job=None
   jobs=self.scan();active=[(j,s) for j,s in jobs if s.get('status') in ACTIVE]
   # An older independently launched worker retains its job lock. Wait for it.
   if any(self._owns_job(j) for j,_ in active):return
   # A crashed or interrupted active job is recovered before later jobs.
   if active:
    job,state=active[0]
    if state.get('status')=='starting' and time.time()-state.get('dispatch_started',0)<30:return
    attempts=state.get('queue_attempts',0)
    if attempts>=2:
     state.update(status='failed',error='Worker stopped repeatedly; inspect worker.log and saved state before resuming');atomic(job/'state.json',state);return
   else:
    queued=[(j,s) for j,s in jobs if s.get('status')=='queued']
    if not queued:return
    job,state=queued[0];attempts=state.get('queue_attempts',0)
   mode=state.get('requested_mode','run');state.update(status='starting',dispatch_started=time.time(),queue_attempts=attempts+1);atomic(job/'state.json',state)
   try:self.worker=self.spawn(job,mode);self.worker_job=job
   except Exception as e:state.update(status='failed',error='Could not start worker: '+str(e));atomic(job/'state.json',state)
 def serve(self):
  self.root.mkdir(parents=True,exist_ok=True)
  try:
   with locked(self.root/'dispatcher.lock'):
    while True:
     try:self.tick()
     except Exception as e:print('Queue error:',str(e),flush=True)
     self.wake.wait(2);self.wake.clear()
  except JobError:print('Another local film dispatcher is already running; this form will not start another.',flush=True)
