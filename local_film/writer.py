"""Local series writer on CPU llama.cpp: arc, script drafts and storyboards."""
import copy,json,os,re,socket,subprocess,time,urllib.request
from pathlib import Path
from .pipeline import JobError,RUNTIME,ROOT
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
MODEL=Path(os.environ.get('LOCAL_FILM_WRITER_MODEL',str(RUNTIME/'models'/'Qwen3.5-9B-UD-Q4_K_XL.gguf')))
WORDS_PER_SECOND=2.7

def _str(value):return isinstance(value,str) and bool(value.strip())

def _record(log_path,event,payload):
 if not log_path:return
 path=Path(log_path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a',encoding='utf8') as f:f.write(json.dumps({'time':time.time(),'event':event,**payload},ensure_ascii=False)+'\n')

def _server(model):
 exe=RUNTIME/'llama'/'llama-server.exe'
 if not exe.is_file() or not Path(model).is_file():raise JobError('Local writer runtime or model missing; run tools/download_series_writer.py and see the installation guide')
 s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
 command=[str(exe),'-m',str(model),'-ngl','0','-c','8192','--host','127.0.0.1','--port',str(port),'--no-webui','--parallel','1']
 return port,command

def _generate(port,command,system,user,schema,name,log_path,validate,max_tokens=3000):
 # llama.cpp runs CPU-only here (-ngl 0); never set -ngl 99, ComfyUI keeps the GPU.
 flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 log_file=Path(log_path).open('ab') if log_path else None
 try:
  proc=subprocess.Popen(command,stdout=log_file or subprocess.DEVNULL,stderr=subprocess.STDOUT,creationflags=flags,cwd=str(ROOT))
  try:
   url=f'http://127.0.0.1:{port}'
   for _ in range(180):
    if proc.poll() is not None:raise JobError('Local writer exited during startup; inspect the writer log')
    try:
     with OPENER.open(url+'/health',timeout=2) as response:
      if response.status==200:break
    except Exception:time.sleep(1)
   else:raise JobError('Local writer did not become ready in time')
   payload={'model':'local-qwen','messages':[{'role':'system','content':system},{'role':'user','content':user}],'temperature':0.4,'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_schema','json_schema':{'name':name,'schema':schema}}}
   for attempt in range(3):
    request=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with OPENER.open(request,timeout=900) as response:answer=json.load(response)
    try:content=answer['choices'][0]['message']['content']
    except (KeyError,IndexError,TypeError):content=None
    _record(log_path,'response',{'attempt':attempt,'content':content})
    data=None
    try:data=json.loads(content)
    except (TypeError,json.JSONDecodeError):pass
    if data is not None and validate(data):return data
    payload['messages'].append({'role':'user','content':'Correction: return only a valid JSON object matching the schema and every stated constraint.'})
   raise JobError(f'Local writer failed to return a valid {name} after two corrections')
  finally:
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 finally:
  if log_file:log_file.close()

def _bible(show,characters):
 cast='\n'.join(f"- {slug} ({c.get('name','')}): {c['description']} Appearance: {c['appearance']}." for slug,c in sorted(characters.items()))
 return (f"Show bible: {show['title']} - {show['logline']}\nBrief: {show['brief']}\nArc: {show['arc_summary']}\n"
  f"Visual style: {show['style']}\nCast (use these ids exactly):\n{cast}")

def draft_cast(show,brief,episodes,log_path):
 schema={'type':'object','properties':{'recurring':{'type':'array','items':{'type':'object','properties':{'slug':{'type':'string'},'name':{'type':'string'},'role':{'type':'string'}},'required':['slug','name','role'],'additionalProperties':False},'minItems':2,'maxItems':2},'episode':{'type':'array','items':{'type':'object','properties':{'number':{'type':'integer'},'name':{'type':'string'},'role':{'type':'string'}},'required':['number','name','role'],'additionalProperties':False},'minItems':episodes,'maxItems':episodes}},'required':['recurring','episode'],'additionalProperties':False}
 def validate(data):
  rec=data.get('recurring');eps=data.get('episode')
  if not isinstance(rec,list)or len(rec)!=2:return False
  if not all(isinstance(x,dict)and isinstance(x.get('slug'),str)and re.fullmatch(r'[a-z0-9][a-z0-9-]*',x['slug'])and _str(x.get('name'))and _str(x.get('role'))for x in rec):return False
  slugs=[x['slug']for x in rec]
  if len(set(slugs))!=2:return False
  return isinstance(eps,list)and len(eps)==episodes and all(type(x.get('number'))is int and _str(x.get('name'))and _str(x.get('role'))for x in eps)
 port,command=_server(MODEL)
 system='You are a local series writer naming characters for a short multi-episode film arc; return JSON only. '
 user=(f"Show bible: {show['title']} - {show['logline']}\nBrief: {brief}\nVisual style: {show['style']}\n"
  f"Series brief: {brief}\nName exactly 2 recurring main characters (slug must be a short lowercase slug) and one character per episode number 1-{episodes}; roles one sentence each.")
 return _generate(port,command,system,user,schema,'cast',log_path,validate,max_tokens=1500)

def draft_arc(show,characters,brief,episodes,log_path):
 schema={'type':'object','properties':{'episodes':{'type':'array','items':{'type':'object','properties':{'number':{'type':'integer'},'brief':{'type':'string'},'ending_note':{'type':'string'}},'required':['number','brief','ending_note'],'additionalProperties':False},'minItems':episodes,'maxItems':episodes}},'required':['episodes'],'additionalProperties':False}
 def validate(data):
  items=data.get('episodes')
  return isinstance(items,list) and len(items)==episodes and all(type(x.get('number'))is int and isinstance(x.get('brief'),str)and len(x['brief'].strip())>=40 and _str(x.get('ending_note')) for x in items)
 port,command=_server(MODEL)
 system='You are a local series writer planning a short multi-episode film arc for a closed prototype. '
 user=(f"{_bible(show,characters)}\nSeries brief: {brief}\nPlan exactly {episodes} episodes. Each brief must be a self-contained paragraph "
  "that ends further along the arc than the previous one and names an ending_note that hands continuity to the next episode.")
 return _generate(port,command,system,user,schema,'story_arc',log_path,validate,max_tokens=1500)

def draft_script(show,characters,arc_md,continuity_prev,ep_brief,target_seconds,log_path):
 cast=sorted(characters);budget=int(target_seconds*WORDS_PER_SECOND)
 schema={'type':'object','properties':{'title':{'type':'string','minLength':3},'synopsis':{'type':'string','minLength':20},'lines':{'type':'array','minItems':3,'maxItems':12,'items':{'type':'object','properties':{'scene':{'type':'string','minLength':8},'setting':{'type':'string','minLength':8},'action':{'type':'string','minLength':12},'dialogue':{'type':'array','items':{'type':'object','properties':{'character':{'type':'string','enum':cast},'text':{'type':'string','minLength':1}},'required':['character','text'],'additionalProperties':False}}},'required':['scene','setting','action','dialogue'],'additionalProperties':False}},'ending_state':{'type':'string','minLength':20},'next_hook':{'type':'string','minLength':10}},'required':['title','synopsis','lines','ending_state','next_hook'],'additionalProperties':False}
 def validate(data):
  lines=data.get('lines')
  if not isinstance(lines,list)or not 3<=len(lines)<=12:return False
  if not all(isinstance(x,dict)and all(_str(x.get(k))for k in('scene','setting','action'))and isinstance(x.get('dialogue'),list)and x['dialogue']and all(isinstance(l,dict)and l.get('character')in cast and _str(l.get('text'))for l in x['dialogue'])for x in lines):return False
  if not all(_str(data.get(k))for k in('title','synopsis','ending_state','next_hook')):return False
  words=sum(len(l['text'].split())for x in lines for l in x['dialogue'])
  return words<=budget*1.3
 previous=continuity_prev.get('ending_state','') if isinstance(continuity_prev,dict) else str(continuity_prev or '')
 system=('You are a local series writer for a closed prototype. '
  f"Keep the total spoken words under {budget} (about {WORDS_PER_SECOND} words per second of a {target_seconds}-second episode). "
  'Return 3 to 12 lines; each line becomes one filmed shot. Speakers must be cast ids. '
  'Write ending_state as the authoritative physical and emotional position at the end of this episode, '
  'and next_hook as one line teasing the next episode.')
 if previous:system+=' Authoritative continuity from the previous episode: '+previous
 user=(f"{_bible(show,characters)}\nStory arc:\n{arc_md}\nEpisode brief: {ep_brief}\n"
  +(('Continuing directly from: '+previous+'\n')if previous else '')
  +f"Target spoken duration: {target_seconds} seconds (about {budget} spoken words).")
 port,command=_server(MODEL)
 return _generate(port,command,system,user,copy.deepcopy(schema),'episode_script',log_path,validate)

def storyboard(show,characters,script,log_path,number=None,target_seconds=0,episode_id=None):
 style=show['style'];cast=list(show['characters']);shots=[]
 def present(line,index):
  names={l['character'] for l in line['dialogue']}
  text=' '.join(line.get(k,'')for k in('scene','setting','action'))
  for slug in cast:
   word=characters[slug].get('name')or slug
   if slug in names or slug.lower()in text.lower() or word.lower()in text.lower():names.add(slug)
  return[slug for slug in cast if slug in names]
 for i,line in enumerate(script['lines']):
  ids=present(line,i);speakers=[]
  for l in line['dialogue']:
   if l['character']not in speakers:speakers.append(l['character'])
  identities=''.join(f"{characters[slug].get('name',slug)}: {characters[slug]['description']} {characters[slug]['appearance']}. "for slug in ids)
  prompt=f"{line['setting']}. Medium shot, locked camera. {identities}{line['action']} Visual style: {style}."
  if i+1<len(script['lines']):
   nxt=script['lines'][i+1]
   continuation=f"Carry the moment forward toward: {nxt['action']}. Do not restart or repeat actions already completed."
  else:continuation=f"Reach the episode's final position: {script['ending_state']} Hold it as the closing frame without restarting."
  shots.append({'id':f'shot-{i+1:02}','scene':line['scene'],'setting':line['setting'],'action':line['action'],'continuation_action':continuation,'prompt':prompt,'characters':ids,'speakers':speakers,'dialogue':copy.deepcopy(line['dialogue'])})
 episode={'id':episode_id or f"{number:02d}-episode",'number':number,'title':script['title'],'target_seconds':target_seconds,'shots':shots,'synopsis':script['synopsis'],'ending_state':script['ending_state'],'next_hook':script['next_hook']}
 _record(log_path,'storyboard',{'episode':episode})
 return episode
