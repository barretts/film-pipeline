"""Local planning with a CPU llama.cpp server; no remote inference."""
import copy,json,os,socket,subprocess,time,urllib.request
from pathlib import Path
from .references import character_reference_guidance
ROOT=Path(__file__).resolve().parent.parent
RUNTIME=ROOT/'local-runtime'
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
SCHEMA={"type":"object","properties":{"character":{"type":"string"},"shots":{"type":"array","items":{"type":"object","properties":{"scene":{"type":"string"},"action":{"type":"string"},"continuation_action":{"type":"string"},"prompt":{"type":"string"}},"required":["scene","action","continuation_action","prompt"],"additionalProperties":False}}},"required":["character","shots"],"additionalProperties":False}

def plan(brief,script_parts,style,log_path,has_reference=False,segment_instructions='',reference_creativity=0):
 exe=RUNTIME/'llama'/'llama-server.exe';model=RUNTIME/'models'/'Qwen3.5-4B-Q4_K_M.gguf'
 if not exe.is_file() or not model.is_file():raise FileNotFoundError('Local planner runtime or model missing; see installation guide')
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 command=[str(exe),'-m',str(model),'-ngl','0','-c','4096','--host','127.0.0.1','--port',str(port),'--no-webui','--parallel','1']
 flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 with Path(log_path).open('ab') as log:
  proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,creationflags=flags,cwd=str(ROOT))
  try:
   url=f'http://127.0.0.1:{port}'
   for _ in range(120):
    if proc.poll() is not None:raise RuntimeError('Local planner exited during startup; inspect planner.log')
    try:
     with OPENER.open(url+'/health',timeout=2) as response:
      if response.status==200:break
    except Exception:time.sleep(1)
   else:raise TimeoutError('Local planner did not become ready')
   system=('You are a local film shot planner. Return JSON matching the schema. '
           'Return exactly one shot per numbered script part, in the same order. '
           'Describe a visually consistent adult character and clear filmable actions. '
           'The prompt must include appearance, setting, style, action, and speaking to camera. '
           'For continuation_action, describe what happens after the first action, without restarting or repeating it. '
           'Instructions for every segment are mandatory constraints for all shots and continuations. Do not contradict them or invent camera movements. '
           'Do not invent additional shots or narration.')
   if has_reference:
    if reference_creativity>0:system+=' A character reference will be supplied to the video model. You cannot see it. Do not claim to observe its features. '+character_reference_guidance(reference_creativity)
    else:system+=' A reference image is provided and is authoritative: preserve its person, clothing, colors and styling. Do not invent hair, costume or visual features; describe them only as the character from the reference image.'
   user='Creative brief: '+brief+'\nVisual style: '+style+'\nScript parts:\n'+'\n'.join(f'{i+1}. {part}' for i,part in enumerate(script_parts))
   if segment_instructions.strip():user+='\nInstructions for every segment (authoritative):\n'+segment_instructions
   schema=copy.deepcopy(SCHEMA);schema['properties']['shots'].update(minItems=len(script_parts),maxItems=len(script_parts));schema['properties']['character']['minLength']=15
   for field,minimum in [('scene',12),('action',12),('continuation_action',12),('prompt',30)]:schema['properties']['shots']['items']['properties'][field]['minLength']=minimum
   payload={'model':'local-qwen','messages':[{'role':'system','content':system},{'role':'user','content':user}], 'temperature':0.2,'max_tokens':1500,'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_schema','json_schema':{'name':'shot_plan','schema':schema}}}
   for attempt in range(2):
    req=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with OPENER.open(req,timeout=300) as response:answer=json.load(response)
    try:data=json.loads(answer['choices'][0]['message']['content'])
    except (json.JSONDecodeError,KeyError,IndexError,TypeError):
     payload['messages'].append({'role':'user','content':'Correction: return only a valid JSON object matching the schema.'});continue
    if isinstance(data.get('character'),str) and len(data['character'].strip())>=15 and len(data.get('shots',[]))==len(script_parts) and all(all(isinstance(s.get(k),str) and len(s[k].strip())>=m for k,m in [('scene',12),('action',12),('continuation_action',12),('prompt',30)]) for s in data['shots']):return data
    payload['messages'].append({'role':'user','content':f'Correction: exactly {len(script_parts)} shots are required. Return all required fields.'})
   raise ValueError('Planner failed to return one valid shot per script part after two attempts')
  finally:
   proc.terminate()
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
