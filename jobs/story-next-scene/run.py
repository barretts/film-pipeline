import copy,json,shutil,subprocess,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from local_film import pipeline as P,series as S,characters as C
ROOT=Path(__file__).resolve().parent
MAN=P.load(ROOT/'plan.json');SOURCE=Path(MAN['source_job']);STATE=ROOT/'execution.json'

def save(data):P.atomic(STATE,data)
def note(s):print(time.strftime('%H:%M:%S'),s,flush=True)
def render(beat,index,guide,attempt,correction=''):
 name=f"story-next-{beat['id']}-take{attempt}";out=ROOT/(name+'.mp4')
 if out.exists():raise RuntimeError('Existing take must be reviewed, not overwritten: '+str(out))
 graph=copy.deepcopy(P.load(SOURCE/'state.json')['segments']['shot-01-01']['graph'])
 cfg=P.load(SOURCE/'request.json');show=C.load_show(P.ROOT/'series','signal-in-the-snow');cast=C.load_cast(P.ROOT/'series',show)
 slugs=beat['on_screen_cast'];inputs=graph['157']['inputs']
 for k in list(inputs):
  if k.startswith('ref_images.'):del inputs[k]
 for k in ['170','171']:graph.pop(k,None)
 for slot,slug in enumerate(slugs):
  character=cast[slug];portrait=Path(character['_dir'])/character['portrait'];filename=name+'-'+slug+'.png';shutil.copy2(portrait,P.BASE/'input'/filename)
  graph[str(170+slot)]={'class_type':'LoadImage','inputs':{'image':filename}};inputs[f'ref_images.ref_image_{slot}']=[str(170+slot),0]
 detail=(show['style']+'\n\nStarting story situation: '+json.dumps(beat['before'])+'\nOne continuous shot. '+beat['action']+'\nRequired ending situation: '+json.dumps(beat['after'])+'\nPreserve faces and clothing, while allowing the specified movement and departure. The action happens once and completes within this clip. No reset to an earlier event. ')
 if beat['dialogue']:
  detail+=' '.join(S._dialogue({'dialogue':beat['dialogue']},cast))+' Match only the supplied audio; do not repeat the line.'
 else:detail+='Silent physical action. Closed mouths, no dialogue, no speech or mimed conversation.'
 if correction:detail+='\nCorrection based on prior failed take: '+correction
 inputs['prompt']=S._six_sections(show,cast,slugs,detail);inputs['length']=124
 filename=name+'-guide.png';shutil.copy2(guide,P.BASE/'input'/filename);graph['5']['inputs']['image']=filename
 if beat.get('cut_to_new_location'):
  graph.pop('163',None);graph['19']['inputs']['positive']=['160',0]
 if beat['audio']=='silence':
  audio=ROOT/'silence.wav'
  if not audio.exists():P.run_cmd(['ffmpeg','-y','-v','error','-f','lavfi','-i','anullsrc=r=22050:cl=mono','-t',str(124/24),audio])
 else:audio=Path(beat['audio'])
 filename=name+'.wav';shutil.copy2(audio,P.BASE/'input'/filename);graph['18']['inputs']['audio']=filename;graph['19']['inputs']['start_seconds']=0
 graph['130']['inputs']['noise_seed']=MAN['generation']['seed'];graph['136']['inputs']['filename_prefix']='story-next-smoke/'+name
 record={'beat':beat['id'],'attempt':attempt,'prompt_id':str(uuid.uuid4()),'status':'prepared','graph':graph,'guide':str(guide),'correction':correction}
 path=ROOT/(name+'.json');P.atomic(path,record)
 q=P.api('/queue')
 if q.get('queue_running') or q.get('queue_pending'):raise RuntimeError('GPU queue occupied; refusing concurrent render')
 record['status']='submitting';P.atomic(path,record)
 P.api('/prompt',{'prompt':graph,'prompt_id':record['prompt_id'],'client_id':'story-next-experiment'})
 record['status']='submitted';P.atomic(path,record);note('Submitted '+name)
 deadline=time.monotonic()+720
 while time.monotonic()<deadline:
  status,entry=P.locate(record['prompt_id'])
  if status=='history':break
  if status=='unknown':raise RuntimeError('Ambiguous render outcome; inspect queue/history before any retry')
  time.sleep(10)
 else:
  # Only interrupt the prompt owned by this experiment, never unrelated work.
  q=P.api('/queue')
  if any(row[1]==record['prompt_id'] for row in q.get('queue_running',[])):P.api('/interrupt',{})
  raise RuntimeError('Render timed out after 720 seconds')
 if entry.get('status',{}).get('status_str')!='success':raise RuntimeError('Render failed: '+str(entry.get('status')))
 outputs=[P.BASE/'output'/str(item.get('subfolder',''))/item['filename'] for values in entry['outputs'].values() for key in ['gifs','videos'] for item in values.get(key,[]) if item.get('filename','').endswith('.mp4')]
 if not outputs:raise RuntimeError('No MP4 in output')
 shutil.copy2(outputs[0],out);P.run_cmd(['ffmpeg','-v','error','-xerror','-i',out,'-map','0:v:0','-map','0:a:0','-f','null','-'])
 tail=ROOT/(name+'-tail.png');P.extract_tail(out,tail)
 sheet=ROOT/(name+'-sheet.jpg')
 P.run_cmd([sys.executable,P.ROOT/'tools/contact_sheet.py','--videos',out,'--frames','0,0.2,0.4,0.6,0.8,0.99','--out',sheet,'--title',name])
 record.update(status='awaiting_review',output=str(out),tail=str(tail),sheet=str(sheet));P.atomic(path,record)
 return record

def main():
 progress={'status':'starting','started':time.time(),'approved':[],'renders':0};save(progress)
 failure=None
 try:
  with P.locked(P.JOBS/'pipeline.lock'),P.locked(P.JOBS/'gpu.lock'):
   q=P.api('/queue')
   if q.get('queue_running') or q.get('queue_pending'):raise RuntimeError('ComfyUI queue busy')
   note('Stopping Strata for bounded experiment')
   subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(P.ROOT/'jobs/orbit-smoke/kill-strata.ps1')],check=True)
   request=P.urllib.request.Request(P.ADDR+'/free',data=json.dumps({'unload_models':True,'free_memory':True}).encode(),headers={'Content-Type':'application/json'})
   with P.OPENER.open(request,timeout=30) as response:response.read()
   time.sleep(5)
   guide=Path(MAN['first_guide'])
   retry_used=False
   for index,beat in enumerate(MAN['beats']):
    attempt=1;correction=''
    while True:
     record=render(beat,index,guide,attempt,correction);progress.update(status='awaiting_review',current=record,renders=progress['renders']+1);save(progress)
     decision=ROOT/(f"review-{beat['id']}-take{attempt}.json");deadline=time.monotonic()+300
     note('Awaiting review: '+str(decision))
     while not decision.exists():
      if time.monotonic()>deadline:raise RuntimeError('Review timeout; stopping and restoring Strata')
      time.sleep(2)
     review=P.load(decision)
     if review['decision']=='approve':
      guide=Path(record['tail']);progress['approved'].append(record);break
     if review['decision']=='retry' and not retry_used and review.get('correction'):
      retry_used=True;attempt+=1;correction=review['correction'];note('One changed retry: '+correction);continue
     raise RuntimeError('Story acceptance failed at '+beat['id']+': '+review.get('reason','review rejected'))
   paths=[Path(MAN['approved_cut'])]+[Path(r['output']) for r in progress['approved']]
   req=P.load(SOURCE/'request.json');req['staged_music']=None
   segments=[(p,P.duration(p)) for p in paths]
   # The experiment has its own output directory and never alters the episode.
   output=P.assemble(ROOT,{},req,segments)
   P.run_cmd(['ffmpeg','-v','error','-xerror','-i',output,'-map','0:v:0','-map','0:a:0','-f','null','-'])
   progress.update(status='awaiting_user_playback',output=str(output));save(progress);note('Experiment assembled: '+str(output))
 except Exception as e:
  failure=e;progress.update(status='stopped',error=str(e));save(progress);note(str(e))
 finally:
  note('Restoring Strata')
  with (ROOT/'restore.log').open('w',encoding='utf8') as restore_log:
   r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(P.ROOT/'jobs/orbit-smoke/run.ps1'),'-RestoreOnly'],stdout=restore_log,stderr=subprocess.STDOUT)
  progress['restore_exit']=r.returncode;save(progress);note('Restore exit='+str(r.returncode))
 if failure:raise failure

if __name__=='__main__':main()
