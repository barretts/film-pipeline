import json,time,urllib.request,urllib.error,subprocess,copy
from pathlib import Path
root=Path(r'F:\film-pipeline');local=root/'comfy-local';out=local/'output'/'ref2va-new-reels';op=urllib.request.build_opener(urllib.request.ProxyHandler({}))
items=[('character-02-door','ref2va-character-02-door'),('live-action-02-door','ref2va-live-02-door')]
submitted={};finished={};start=time.time()
def get(path):
 with op.open('http://127.0.0.1:8191/'+path,timeout=10) as r:return json.load(r)
def post(body):
 req=urllib.request.Request('http://127.0.0.1:8191/prompt',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 try:
  with op.open(req,timeout=30) as r:return json.load(r)
 except urllib.error.HTTPError as e: raise RuntimeError(e.read().decode())
while len(finished)<len(items) and time.time()-start<7200:
 for name,tag in items:
  if name in finished:continue
  try:
   if name not in submitted:
    sub=local/(tag+'-submission.json')
    if not sub.exists():continue
    original_id=json.loads(sub.read_text())['response']['prompt_id'];hist=get('history/'+original_id)
    if original_id not in hist:continue
    orig=hist[original_id]
    if orig['status']['status_str']!='success':print('ORIGINAL FAILED',name,flush=True);finished[name]='original failed';continue
    v=orig['outputs']['136']['gifs'][0];video=local/'output'/v['subfolder']/v['filename'];tail=local/'input'/f'ref2va-{name}-tail.png'
    subprocess.run(['ffmpeg','-y','-v','error','-sseof','-0.042','-i',str(video),'-frames:v','1',str(tail)],check=True)
    if not tail.exists():raise RuntimeError('No tail frame')
    g=json.loads((local/(tag+'-graph.json')).read_text());g['5']['inputs']['image']=tail.name;g['157']['inputs']['first_frame']=['142',0];g['157']['inputs']['prompt']='Continue the same scene and character seamlessly from the reference frame. '+g['157']['inputs']['prompt']+' Continue naturally from the previous moment, maintaining wardrobe, setting, and lighting.'
    g['19']['inputs']['start_seconds']=124/24;g['130']['inputs']['noise_seed']+=100;g['136']['inputs']['filename_prefix']=f'ref2va-new-reels/{name}-continuation'
    graphfile=local/(tag+'-continuation-graph.json');graphfile.write_text(json.dumps(g,indent=2))
    response=post({'prompt':g,'client_id':'ref2va-extended-reels'});submitted[name]=(response['prompt_id'],str(video));(local/(tag+'-continuation-submission.json')).write_text(json.dumps({'response':response,'graph':g},indent=2));print('QUEUED CONTINUATION',name,response['prompt_id'],flush=True)
   else:
    pid,first=submitted[name];hist=get('history/'+pid)
    if pid not in hist:continue
    entry=hist[pid];(local/(tag+'-continuation-result.json')).write_text(json.dumps(entry,indent=2))
    if entry['status']['status_str']!='success':print('CONTINUATION FAILED',name,json.dumps(entry['status'])[:800],flush=True);finished[name]='continuation failed';continue
    second=out/entry['outputs']['136']['gifs'][0]['filename'];dest=out/f'{name}-extended-reel.mp4'
    filters='[0:v]crop=704:1252:0:14,scale=1080:1920:flags=lanczos,setsar=1[v0];[1:v]crop=704:1252:0:14,scale=1080:1920:flags=lanczos,setsar=1[v1];[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]'
    subprocess.run(['ffmpeg','-y','-v','error','-i',first,'-i',str(second),'-filter_complex',filters,'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(dest)],check=True)
    finished[name]=str(dest);print('EXTENDED READY',name,str(dest),flush=True)
  except Exception as e:
   print('FAILED',name,type(e).__name__,str(e)[:600],flush=True);finished[name]='error: '+str(e)
 time.sleep(10)
(local/'ref2va-door-extended-results.json').write_text(json.dumps(finished,indent=2));print('FINISHED',json.dumps(finished),flush=True)
