import json,time,urllib.request,urllib.error,subprocess,sys
from pathlib import Path
root=Path(r'F:\film-pipeline\comfy-local')
tag = sys.argv[1] if len(sys.argv) > 1 else 'ref2va-comparison'
g=json.loads((root/(tag+'-graph.json')).read_text(encoding='utf-8'))
op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
body=json.dumps({'prompt':g,'client_id':'ref2va-controlled-quality-test'}).encode()
t0=time.time()
try:
 r=json.load(op.open(urllib.request.Request('http://127.0.0.1:8191/prompt',data=body,headers={'Content-Type':'application/json'}),timeout=30))
except urllib.error.HTTPError as e:
 print('VALIDATION ERROR',e.code,e.read().decode(),flush=True);raise
(root/(tag+'-submission.json')).write_text(json.dumps({'submitted':t0,'response':r,'graph':g},indent=2),encoding='utf-8')
pid=r['prompt_id'];print('SUBMITTED',pid,flush=True)
peak=0
while True:
 try:
  sm=subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
  peak=max(peak,int(sm.stdout.strip().splitlines()[0]))
  history=json.load(op.open('http://127.0.0.1:8191/history/'+pid,timeout=5))
  if pid in history:
   record=history[pid];record['wall_seconds']=time.time()-t0;record['peak_gpu_mib_sampled']=peak
   (root/(tag+'-result.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
   print('FINISHED',json.dumps({'elapsed_seconds':record['wall_seconds'],'peak_gpu_mib':peak,'status':record.get('status'),'outputs':record.get('outputs')}),flush=True); break
  print('RUNNING',int(time.time()-t0),'sec, peak GPU',peak,'MiB',flush=True)
 except Exception as e: print('POLL',str(e),flush=True)
 time.sleep(20)
