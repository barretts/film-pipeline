# Post-fix companion to probe.py. probe.py hard-codes the BUG-side expectations
# (zero-retry run returning normally, departure chain validating), so the fixed code
# makes it raise. This companion runs the same five probes and records the corrected
# behaviour, refusing paths included. The original probe.py and probes.json stay untouched.
import importlib.util,json,tempfile,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from local_film import directing as D
spec=importlib.util.spec_from_file_location('fixture',ROOT/'tests/test_local_film_directing.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
results={}
# 1) Full managed orchestration with all GPU-side operations mocked.
t=F.OrchestratorTests()
try:
 with patch.object(D.subprocess,'run') as proc,patch.object(D.P,'locked') as locks:
  _,job,result,submit=t._run('managed')
  results['managed_lifecycle']={'render_calls':submit.call_count,'subprocess_calls':proc.call_count,'lock_calls':locks.call_count}
finally:t.doCleanups()
# 2) Zero changed-retry budget must reject with no second render (refusal expected).
t=F.OrchestratorTests()
try:
 _,job,result,submit=t._run('managed',gates=[{'decision':'retry','correction':'changed camera'},{'decision':'approve'}],plan_overrides={'max_changed_retries':0},expect_error='changed-retry budget exhausted')
 results['zero_retry_budget']={'render_calls':submit.call_count,'refused':result['error'],'ledger':D.P.load(job/'story_state.json')}
finally:t.doCleanups()
# 3) A previously submitted prompt must be reconciled, not overwritten with another UUID.
with tempfile.TemporaryDirectory() as tmp:
 job=Path(tmp);name='existing-take';record={'take_name':name,'graph':F.template(),'guide':None,'audio':'silence','on_screen_cast':[]}
 old={'status':'submitted','prompt_id':'original-prompt-id'};D.P.atomic(job/(name+'.json'),old);sent=[];looked=[]
 def api(path,payload=None):
  if path=='/queue':return {'queue_running':[],'queue_pending':[]}
  if path=='/prompt':sent.append(payload['prompt_id']);return {}
  raise AssertionError(path)
 def locate(pid):
  looked.append(pid);return 'history',{'status':{'status_str':'success'},'outputs':{'136':{'gifs':[{'filename':'fake.mp4'}]}}}
 with patch.object(D,'silence_wav'),patch.object(D.shutil,'copy2'):
  D.submit_take({},record,F.SHOW,F.CAST,job,api=api,locate=locate,clock=lambda:0,sleep=lambda s:None)
 results['previous_submission']={'original_prompt_id':old['prompt_id'],'new_submissions':sent,'history_lookups':looked,'persisted':D.P.load(job/(name+'.json'))['prompt_id'],'persisted_status':D.P.load(job/(name+'.json'))['status']}
# 4) Off-screen departure erasure must now be refused (fix 3).
first=F.beat()
second=F.beat(id='erase_departure',before=dict(first['after']),after={'james':'inside','kate':'inside'},on_screen_cast=['kate'],action='Kate listens alone.')
third=F.beat(id='reappear',before=dict(second['after']),after=dict(second['after']),on_screen_cast=['kate','james'],action='James talks to Kate.')
p=D.normalize_plan(F.plan(beats=[first,second,third]))
try:
 D.validate(p,set(F.CAST));results['departure_erasure']={'validated':True}
except D.DirectiveError as error:results['departure_erasure']={'validated':False,'refused':str(error)}
# 5) Snapshot-approved entries plus a plan revision must refuse a new take for the approved beat.
with tempfile.TemporaryDirectory() as tmp:
 ledger=D.StoryLedger(first['before']);ledger.append({'beat':first['id'],'decision':'approve','after':first['after']},Path(tmp)/'ledger.json')
 p=D.normalize_plan(F.plan());p['_template']=F.template()
 try:D.plan_take(p,first,F.SHOW,F.CAST,ledger.state,None,1);results['resume_after_approval']={'unexpected':'planned over approved state'}
 except D.DirectiveError as e:results['resume_after_approval']={'error':str(e)}
(ROOT/'jobs/directive-review/probes-post-fix.json').write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps({k:({a:b for a,b in v.items() if a!='ledger'} if isinstance(v,dict) else v) for k,v in results.items()},indent=2))
