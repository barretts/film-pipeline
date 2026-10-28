"""Loopback-only form and job launcher for the local film pipeline."""
import html,json,os,subprocess,sys,threading,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from .pipeline import JOBS,ROOT,atomic,create,load,locked,JobError
PORT=int(os.environ.get('LOCAL_FILM_PORT','8765'))
PAGE='''<!doctype html><html><head><meta charset="utf-8"><title>Local Film Pipeline</title><style>body{max-width:850px;margin:2em auto;font:16px system-ui;padding:0 1em;background:#101622;color:#e8edf3}label{display:block;margin:1em 0 .3em}input,textarea,select,button{font:inherit;padding:.6em;border-radius:5px;border:1px solid #637085}textarea,input{box-sizing:border-box;width:100%;background:#1e293b;color:white}button{cursor:pointer;background:#80c0f0;color:#101622;margin:.6em .4em .6em 0}small{color:#b5c5d8}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1e293b;padding:1em}</style></head><body><h1>Local Film Pipeline</h1><p>Create a local job. Models run on this computer; completed videos and review evidence are saved in a new job folder.</p><form id="form"><label>Creative brief</label><textarea name="brief" required rows="3" placeholder="A mysterious transmission arrives in a quiet room."></textarea><label>Script</label><textarea name="script" required rows="5" placeholder="The signal came from the other side of the door."></textarea><label>Visual style</label><input name="style" required value="cinematic hand-drawn anime"><label>Character reference image paths (optional; one per line)</label><textarea name="references" rows="2" placeholder="F:\\images\\character.png"></textarea><label>Local music file path (optional)</label><input name="music" placeholder="F:\\audio\\music.wav"><small>Music is mixed quietly underneath speech. Leave empty for narration only.</small><label>Output width and height</label><input name="width" type="number" value="1080" min="256" max="3840" step="2"><input name="height" type="number" value="1920" min="256" max="3840" step="2"><label>Frame rate</label><select name="fps"><option>24</option><option>25</option><option>30</option></select><label>Target seconds (optional; 0 = fit narration)</label><input name="duration_seconds" type="number" value="0" min="0" max="180" step="0.1"><button type="submit">Start job</button><button type="button" id="plan">Make editable plan only</button></form><p id="message"></p><section id="job" hidden><h2>Job</h2><pre id="status"></pre><button id="refresh">Refresh</button><button id="loadPlan">Open plan editor</button><button id="run">Run / resume</button><div id="editor" hidden><label>Edit shot plan JSON</label><textarea id="planText" rows="18"></textarea><button id="savePlan">Save plan</button><small>Save edits before running. Do not change a plan after its voice or video generation has begun.</small></div></section><script>
let current='';async function api(url,opts){let r=await fetch(url,opts);let j=await r.json();if(!r.ok)throw Error(j.error||r.status);return j}function payload(){let f=new FormData(document.querySelector('#form'));return {brief:f.get('brief'),script:f.get('script'),style:f.get('style'),references:f.get('references').split('\\n').map(x=>x.trim()).filter(Boolean),music:f.get('music').trim(),width:Number(f.get('width')),height:Number(f.get('height')),fps:Number(f.get('fps')),duration_seconds:Number(f.get('duration_seconds'))}}async function create(mode){try{let j=await api('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request:payload(),mode})});current=j.job_id;document.querySelector('#job').hidden=false;document.querySelector('#message').textContent='Job created: '+current;await refresh()}catch(e){document.querySelector('#message').textContent=e.message}}document.querySelector('#form').onsubmit=e=>{e.preventDefault();create('run')};document.querySelector('#plan').onclick=()=>create('plan');async function refresh(){if(!current)return;try{let s=await api('/api/jobs/'+current);document.querySelector('#status').textContent=JSON.stringify(s,null,2)}catch(e){document.querySelector('#message').textContent=e.message}}document.querySelector('#refresh').onclick=refresh;document.querySelector('#run').onclick=async()=>{try{await api('/api/jobs/'+current+'/run',{method:'POST'});await refresh()}catch(e){document.querySelector('#message').textContent=e.message}};document.querySelector('#loadPlan').onclick=async()=>{try{let p=await api('/api/jobs/'+current+'/plan');document.querySelector('#planText').value=JSON.stringify(p,null,2);document.querySelector('#editor').hidden=false}catch(e){document.querySelector('#message').textContent=e.message}};document.querySelector('#savePlan').onclick=async()=>{try{await api('/api/jobs/'+current+'/plan',{method:'PUT',headers:{'Content-Type':'application/json'},body:document.querySelector('#planText').value});document.querySelector('#message').textContent='Plan saved.'}catch(e){document.querySelector('#message').textContent=e.message}};setInterval(refresh,5000)
</script></body></html>'''

def spawn(job,mode):
 log=(job/'worker.log').open('ab');kwargs={'cwd':str(ROOT),'stdout':log,'stderr':subprocess.STDOUT,'creationflags':getattr(subprocess,'CREATE_NO_WINDOW',0)}
 try:proc=subprocess.Popen([sys.executable,'-m','local_film.pipeline',mode,str(job)],**kwargs)
 finally:log.close()
 return proc.pid
class Handler(BaseHTTPRequestHandler):
 def send_json(self,obj,status=200):
  data=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def job(self,ident):
  if not ident or not all(c.isalnum() or c=='-' for c in ident):raise ValueError('Invalid job id')
  p=JOBS/ident
  if not (p/'state.json').exists():raise FileNotFoundError('Job not found')
  return p
 def body(self):
  n=int(self.headers.get('Content-Length','0'))
  if n>2_000_000:raise ValueError('Request too large')
  return json.loads(self.rfile.read(n))
 def do_GET(self):
  try:
   path=urllib.parse.urlsplit(self.path).path;parts=path.strip('/').split('/')
   if path=='/':
    data=PAGE.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
   if len(parts)>=3 and parts[:2]==['api','jobs']:
    job=self.job(parts[2]);self.send_json(load(job/'plan.json') if len(parts)==4 and parts[3]=='plan' else load(job/'state.json'));return
   self.send_json({'error':'Not found'},404)
  except Exception as e:self.send_json({'error':str(e)},400)
 def do_POST(self):
  try:
   parts=urllib.parse.urlsplit(self.path).path.strip('/').split('/')
   if parts==['api','jobs']:
    data=self.body();mode=data.get('mode','run')
    if mode not in ('run','plan'):raise ValueError('Invalid mode')
    job=create(data['request']);state=load(job/'state.json');state['requested_mode']=mode;atomic(job/'state.json',state);self.send_json({'job_id':job.name,'worker_pid':spawn(job,mode)},201);return
   if len(parts)==4 and parts[:2]==['api','jobs'] and parts[3]=='run':
    job=self.job(parts[2]);state=load(job/'state.json')
    if state.get('status')=='complete':self.send_json({'status':'complete'});return
    if state.get('status') not in ('planned','failed'):raise ValueError('Job is already active')
    state['status']='starting';state['requested_mode']='run';atomic(job/'state.json',state);self.send_json({'worker_pid':spawn(job,'run')});return
   self.send_json({'error':'Not found'},404)
  except Exception as e:self.send_json({'error':str(e)},400)
 def do_PUT(self):
  try:
   parts=urllib.parse.urlsplit(self.path).path.strip('/').split('/')
   if len(parts)!=4 or parts[:2]!=['api','jobs'] or parts[3]!='plan':raise ValueError('Invalid path')
   job=self.job(parts[2]);state=load(job/'state.json')
   if state['status']!='planned':raise ValueError('Plan can only be edited while job is planned and before rendering')
   plan=self.body();shots=plan.get('shots')
   if not isinstance(shots,list) or not shots:raise ValueError('Plan needs at least one shot')
   ids=[]
   for shot in shots:
    if not isinstance(shot,dict) or not all(isinstance(shot.get(k),str) and shot[k].strip() for k in ('id','narration','character','scene','action','prompt')):raise ValueError('Each shot needs id, narration, character, scene, action and prompt')
    if not shot['id'].startswith('shot-') or len(shot['id'])!=7 or not shot['id'][5:].isdigit():raise ValueError('Shot ids must be shot-01 through shot-99')
    ids.append(shot['id'])
   if len(set(ids))!=len(ids):raise ValueError('Shot ids must be unique')
   atomic(job/'plan.json',plan);self.send_json({'saved':True})
  except Exception as e:self.send_json({'error':str(e)},400)
def main():
 JOBS.mkdir(exist_ok=True);server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 for state_file in JOBS.glob('*/state.json'):
  try:
   state=load(state_file)
   if state.get('status') not in ('created','starting','planning','voicing','waiting_for_gpu','rendering','assembling','checking'):continue
   with locked(state_file.parent/'job.lock'):spawn(state_file.parent,'plan' if state.get('requested_mode')=='plan' else 'run')
   print('Resuming',state_file.parent.name,flush=True)
  except (JobError,OSError,ValueError):pass
 print(f'Local film form: http://127.0.0.1:{PORT}',flush=True)
 if os.environ.get('LOCAL_FILM_OPEN_BROWSER')=='1':
  import webbrowser
  webbrowser.open(f'http://127.0.0.1:{PORT}')
 server.serve_forever()
if __name__=='__main__':main()
