import contextlib
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from local_film import directing as D
from local_film import pipeline as P

SHOW={'style':'cold polar palette','characters':['kate','james'],'soundscape':'wind','music':'strings'}
CAST={'kate':{'name':'Kate','description':'a woman','appearance':'navy wool jacket','portrait':'kate.png','_dir':'.'},
 'james':{'name':'James','description':'a man','appearance':'red parka','portrait':'james.png','_dir':'.'}}

def beat(**overrides):
 base={'id':'exit','before':{'james':'inside','kate':'inside'},'after':{'james':'missing_offscreen','kate':'inside'},
  'action':'James walks out of the control room into the snow.','on_screen_cast':['james','kate'],
  'dialogue':[],'audio':'silence','acceptance':['James leaves'],'cut':'continuation','re_entry_cast':[],'first_guide':None}
 base.update(overrides);return base

def plan(**overrides):
 base={'id':'t','initial_state':{'james':'inside','kate':'inside'},'max_changed_retries':1,'gpu':'managed','beats':[beat()]}
 base.update(overrides);return base

def template():
 return {'5':{'class_type':'LoadImage','inputs':{'image':'stale.png'}},
  '18':{'class_type':'LoadAudio','inputs':{'audio':'stale.wav'}},
  '19':{'class_type':'TextEncodeH3','inputs':{'positive':['163',0],'start_seconds':3}},
 '130':{'class_type':'KSampler','inputs':{'noise_seed':1}},
 '136':{'class_type':'SaveVideo','inputs':{'filename_prefix':'stale'}},
 '157':{'class_type':'H3ReferenceToVideo','inputs':{'prompt':'stale','length':73,'ref_images.ref_image_0':['170',0],'ref_images.ref_image_1':['171',0]}},
 '160':{'class_type':'TextEncodeH3','inputs':{}},
 '163':{'class_type':'ReferenceToVideoConditioning','inputs':{}},
 '170':{'class_type':'LoadImage','inputs':{'image':'stale-kate.png'}},
 '171':{'class_type':'LoadImage','inputs':{'image':'stale-james.png'}}}

def graph_for(beat_value,tpl=None,**kwargs):
 slugs=[slug for slug in SHOW['characters'] if slug in beat_value['on_screen_cast']]
 kwargs.setdefault('guide_name','guide.png');kwargs.setdefault('audio_name','a.wav')
 kwargs.setdefault('seed',7);kwargs.setdefault('take_name','t-exit-take1');kwargs.setdefault('output_prefix','t/t-exit-take1')
 return D.build_graph(tpl or template(),beat_value,CAST,SHOW,slugs,**kwargs)

class ValidatorTests(unittest.TestCase):
 def test_valid_plan_passes(self):D.validate(D.normalize_plan(plan()),set(CAST))
 def test_unknown_cast_rejected(self):
  p=D.normalize_plan(plan(beats=[beat(on_screen_cast=['james','kate','blob'])]))
  with self.assertRaisesRegex(D.DirectiveError,'unknown cast'):D.validate(p,set(CAST))
 def test_dialogue_with_silence_rejected(self):
  b=beat(dialogue=[{'character':'kate','text':'Follow me.'}],audio='silence')
  with self.assertRaisesRegex(D.DirectiveError,'timed audio recording'):D.validate(D.normalize_plan(plan(beats=[b])),set(CAST))
 def test_dialogue_without_audio_rejected(self):
  b=beat(dialogue=[{'character':'kate','text':'Follow me.'}]);b.pop('audio')
  with self.assertRaisesRegex(D.DirectiveError,'timed audio recording'):D.validate(D.normalize_plan(plan(beats=[b])),set(CAST))
 def test_silent_beat_without_audio_declaration_rejected(self):
  b=beat();b.pop('audio')
  with self.assertRaisesRegex(D.DirectiveError,'declare audio'):D.validate(D.normalize_plan(plan(beats=[b])),set(CAST))
 def test_empty_acceptance_rejected(self):
  with self.assertRaisesRegex(D.DirectiveError,'acceptance'):D.validate(D.normalize_plan(plan(beats=[beat(acceptance=[])])),set(CAST))
 def test_broken_state_chain_rejected(self):
  second=beat(id='follow',before={'james':'inside','kate':'inside'},after={'james':'missing_offscreen','kate':'outside'})
  with self.assertRaisesRegex(D.DirectiveError,'before state must equal'):D.validate(D.normalize_plan(plan(beats=[beat(),second])),set(CAST))
 def test_duplicate_beat_ids_rejected(self):
  with self.assertRaisesRegex(D.DirectiveError,'duplicate beat id'):D.validate(D.normalize_plan(plan(beats=[beat(),beat()])),set(CAST))
 def test_retry_budget_above_one_rejected(self):
  with self.assertRaisesRegex(D.DirectiveError,'max_changed_retries'):D.validate(D.normalize_plan(plan(max_changed_retries=2)),set(CAST))
 def test_invalid_gpu_mode_rejected(self):
  with self.assertRaisesRegex(D.DirectiveError,'gpu'):D.validate(D.normalize_plan(plan(gpu='yes')),set(CAST))
 def test_missing_initial_state_rejected(self):
  p=D.normalize_plan(plan());p['initial_state']={}
  with self.assertRaisesRegex(D.DirectiveError,'initial_state'):D.validate(p,set(CAST))
 def test_departed_character_cannot_reappear_without_reentry(self):
  first=beat();second=beat(id='pursuit',before=dict(first['after']),after={'james':'missing_offscreen','kate':'outside'},on_screen_cast=['kate','james'],action='Kate drags James out.')
  with self.assertRaisesRegex(D.DirectiveError,'cannot be on screen'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_explicit_reentry_allowed(self):
  first=beat();second=beat(id='rescue',before=dict(first['after']),after={'james':'inside','kate':'inside'},on_screen_cast=['kate','james'],re_entry_cast=['james'],action='James staggers back inside.')
  D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_reentry_without_flag_rejected(self):
  first=beat();second=beat(id='rescue',before=dict(first['after']),after={'james':'inside','kate':'inside'},on_screen_cast=['kate','james'],action='James staggers back inside.')
  with self.assertRaisesRegex(D.DirectiveError,'cannot go from departed to present'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_offscreen_departure_erasure_rejected(self):
  # Codex finding 3: a Kate-only beat must not flip James gone->present off screen.
  first=beat();second=beat(id='erase_departure',before=dict(first['after']),after={'james':'inside','kate':'inside'},on_screen_cast=['kate'],action='Kate listens alone.')
  with self.assertRaisesRegex(D.DirectiveError,'off-screen james cannot change state'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_established_state_key_cannot_vanish(self):
  first=beat();second=beat(id='forget',before=dict(first['after']),after={'kate':'outside'},on_screen_cast=['kate'],action='Kate watches the door.')
  with self.assertRaisesRegex(D.DirectiveError,'james dropped out of the after state map'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_duplicate_re_entry_rejected(self):
  first=beat();second=beat(id='rescue',before=dict(first['after']),after={'james':'inside','kate':'inside'},on_screen_cast=['kate','james'],re_entry_cast=['james','james'],action='James staggers back inside.')
  with self.assertRaisesRegex(D.DirectiveError,'duplicate slugs in re_entry_cast'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_non_cast_state_keys_may_change_offscreen(self):
  # 'event' is narrative state, not an actor: off-screen updates stay legal.
  first=beat(before={'james':'inside','kate':'inside','event':'alarm'},after={'james':'missing_offscreen','kate':'inside','event':'alarm'})
  second=beat(id='listen',before=dict(first['after']),after={'james':'missing_offscreen','kate':'inside','event':'silence'},on_screen_cast=['kate'],action='Kate listens.')
  D.validate(D.normalize_plan(plan(beats=[first,second],initial_state={'james':'inside','kate':'inside','event':'alarm'})),set(CAST))
 def test_reentry_must_end_present(self):
  first=beat();second=beat(id='rescue',before=dict(first['after']),after={'james':'missing_outside','kate':'inside'},on_screen_cast=['kate','james'],re_entry_cast=['james'],action='James staggers toward the door.')
  with self.assertRaisesRegex(D.DirectiveError,'must end present'):D.validate(D.normalize_plan(plan(beats=[first,second])),set(CAST))
 def test_reentry_of_present_character_rejected(self):
  b=beat(on_screen_cast=['kate','james'],re_entry_cast=['kate'],after={'james':'inside','kate':'inside'})
  with self.assertRaisesRegex(D.DirectiveError,'not departed'):D.validate(D.normalize_plan(plan(beats=[b])),set(CAST))
 def test_experiment_plan_normalizes_cut_flag(self):
  raw={'beats':[beat()],'initial_state':{'james':'inside','kate':'inside'}};raw['beats'][0].pop('cut');raw['beats'][0]['cut_to_new_location']=True
  p=D.normalize_plan(raw);self.assertEqual(p['beats'][0]['cut'],'new_location');self.assertEqual(p['max_changed_retries'],1)
 def test_experiment_plan_prefix_relative_state(self):
  # The declared initial_state holds at the START of the approved prefix; the ledger must
  # begin at the first beat's before state so the strict chain rule still catches real drift.
  first=beat(before={'james':'missing_offscreen','kate':'outside'},after={'james':'missing_offscreen','kate':'advancing'},on_screen_cast=['kate'])
  raw={'id':'x','source_job':'src','approved_cut':'cut.mp4','initial_state':{'james':'inside','kate':'inside'},'beats':[first]}
  p=D.normalize_plan(raw)
  self.assertEqual(p['initial_state'],first['before']);self.assertEqual(p['prefix_declared_state'],{'james':'inside','kate':'inside'})
  self.assertEqual(p['prefix_clips'],['cut.mp4']);self.assertIn('state_note',p)
  D.validate(p,set(CAST))

class LedgerTests(unittest.TestCase):
 def test_state_advances_only_on_approval(self):
  ledger=D.StoryLedger({'james':'inside'})
  ledger.append({'beat':'exit','decision':'reject','after':{'james':'missing_offscreen'}},Path('memory'))
  self.assertEqual(ledger.state['james'],'inside')
  ledger.append({'beat':'exit','decision':'approve','after':{'james':'missing_offscreen'}},Path('memory'))
  self.assertEqual(ledger.state['james'],'missing_offscreen');self.assertIn('james',ledger.departed)
 def test_append_persists_and_reloads(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'story_state.json';ledger=D.StoryLedger({'james':'inside'})
   ledger.append({'beat':'exit','decision':'approve','after':{'james':'missing_offscreen'}},path)
   again=D.StoryLedger.load(path,{'james':'inside'})
   self.assertEqual(again.state,{'james':'missing_offscreen'});self.assertEqual(len(again.entries),1)
 def test_initial_state_mismatch_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'story_state.json';D.StoryLedger({'james':'inside'}).append({'beat':'x','decision':'approve','after':{'kate':'outside'}},path)
   with self.assertRaisesRegex(D.DirectiveError,'different initial_state'):D.StoryLedger.load(path,{'james':'elsewhere'})

class GraphTests(unittest.TestCase):
 def test_slots_follow_show_order_and_explicit_cast(self):
  graph=graph_for(beat(on_screen_cast=['james','kate']))
  inputs=graph['157']['inputs']
  self.assertEqual(inputs['ref_images.ref_image_0'][0],'170');self.assertEqual(graph['170']['inputs']['image'],'t-exit-take1-kate.png')
  self.assertEqual(graph['171']['inputs']['image'],'t-exit-take1-james.png')
  self.assertEqual(sorted(k for k in inputs if k.startswith('ref_images.')),['ref_images.ref_image_0','ref_images.ref_image_1'])
 def test_absent_cast_slot_removed(self):
  graph=graph_for(beat(on_screen_cast=['kate']))
  self.assertNotIn('171',graph);self.assertEqual(sorted(k for k in graph['157']['inputs'] if k.startswith('ref_images.')),['ref_images.ref_image_0'])
 def test_new_location_cut_drops_conditioning_and_rewires(self):
  graph=graph_for(beat(cut='new_location'))
  self.assertNotIn('163',graph);self.assertEqual(graph['19']['inputs']['positive'],['160',0])
 def test_continuation_keeps_conditioning(self):
  graph=graph_for(beat(cut='continuation'))
  self.assertIn('163',graph);self.assertEqual(graph['19']['inputs']['positive'],['163',0])
 def test_wiring_values(self):
  graph=graph_for(beat(),seed=2801)
  self.assertEqual(graph['5']['inputs']['image'],'guide.png');self.assertEqual(graph['18']['inputs']['audio'],'a.wav')
  self.assertEqual(graph['19']['inputs']['start_seconds'],0);self.assertEqual(graph['130']['inputs']['noise_seed'],2801)
  self.assertEqual(graph['136']['inputs']['filename_prefix'],'t/t-exit-take1');self.assertEqual(graph['157']['inputs']['length'],124)
 def test_missing_required_node_refused(self):
  tpl=template();tpl.pop('18')
  with self.assertRaisesRegex(D.DirectiveError,'missing node 18'):graph_for(beat(),tpl=tpl)

class PromptTests(unittest.TestCase):
 def test_silent_beat_clause(self):
  prompt=D.compose_prompt(beat(),SHOW,CAST,['kate','james'])
  self.assertIn('Closed mouths, no dialogue',prompt);self.assertNotIn('<d>',prompt)
  self.assertIn('action happens once and completes within this clip',prompt);self.assertIn('No reset to an earlier event',prompt)
 def test_states_included_verbatim(self):
  prompt=D.compose_prompt(beat(),SHOW,CAST,['kate','james'])
  self.assertIn('Starting story situation: '+json.dumps(beat()['before']),prompt)
  self.assertIn('Required ending situation: '+json.dumps(beat()['after']),prompt)
 def test_dialogue_clause(self):
  b=beat(dialogue=[{'character':'kate','text':'Follow me.'}],audio='voice.wav')
  prompt=D.compose_prompt(b,SHOW,CAST,['kate','james'])
  self.assertIn('Kate (S1) says <d>[English] Follow me. </d>',prompt);self.assertIn('do not repeat the line',prompt)
  self.assertNotIn('Closed mouths',prompt)
 def test_correction_appended(self):
  prompt=D.compose_prompt(beat(),SHOW,CAST,['kate','james'],'lock the camera on the station wall')
  self.assertIn('Correction based on prior failed take: lock the camera on the station wall',prompt)

class ReviewGateTests(unittest.TestCase):
 def test_missing_correction_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'review.json';path.write_text(json.dumps({'decision':'retry'}),encoding='utf8')
   with self.assertRaisesRegex(D.DirectiveError,'documented correction'):D.review_gate(path)
 def test_invalid_decision_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'review.json';path.write_text(json.dumps({'decision':'maybe'}),encoding='utf8')
   with self.assertRaisesRegex(D.DirectiveError,'approve, retry or reject'):D.review_gate(path)
 def test_timeout_without_decision(self):
  times=iter([0,0,1000])
  with self.assertRaisesRegex(D.DirectiveError,'Review timeout'):D.review_gate(Path('missing-review.json'),100,clock=times.__next__,sleep=lambda s:None)
 def test_approve_loaded(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'review.json';path.write_text(json.dumps({'decision':'approve','evidence':['ok']}),encoding='utf8')
   self.assertEqual(D.review_gate(path)['evidence'],['ok'])

class CorrelationTests(unittest.TestCase):
 def setUp(self):
  import random
  rng=random.Random(3)
  self.source=[rng.uniform(-1.0,1.0) for _ in range(2000)]
 def test_shifted_source_matched_within_window(self):
  source=self.source[:500]
  mix=[0.0]*4+source
  score,lag=D.best_correlation(source,mix)
  self.assertGreater(score,0.999);self.assertEqual(lag,4)
 def test_shift_beyond_window_not_matched(self):
  mix=[0.0]*200+self.source
  score,_=D.best_correlation(self.source,mix)
  self.assertLess(score,0.5)
 def test_silence_scores_none(self):
  score,lag=D.best_correlation([0.0]*800,[0.0]*800)
  self.assertIsNone(score)

class SilenceTests(unittest.TestCase):
 def test_generated_once_and_never_regenerated(self):
  if not shutil.which('ffmpeg'):self.skipTest('FFmpeg required')
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'silence.wav';D.silence_wav(path,124/24)
   first=path.read_bytes();self.assertGreater(len(first),1000)
   path.write_bytes(b'kept-marker')
   D.silence_wav(path,124/24)
   self.assertEqual(path.read_bytes(),b'kept-marker')

class AuditTests(unittest.TestCase):
 def _job(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);job=Path(tmp.name);(job/'take-1.mp4').write_bytes(b'v');return job
 def test_dialogue_audit_computes_correlation(self):
  job=self._job();beat_value=beat(dialogue=[{'character':'kate','text':'Go.'}],audio='voice.wav')
  calls=[]
  def run(args,**kwargs):calls.append([str(a) for a in args]);return type('r',(),{'stdout':b''})()
  source=[0.5,-0.25]*400;mix=[0.0]*4+source
  with patch.object(D.P,'extract_tail'),patch.object(D.P,'audio_vector',side_effect=[source,mix]):
   out=D.audit_take(job/'take-1.mp4',beat_value,job,dialogue_wav=Path('voice.wav'),run=run)
  self.assertGreater(out['audio']['correlation'],0.999);self.assertEqual(out['audio']['lag_samples'],4)
  self.assertTrue(any('tile=4x4' in ' '.join(call) for call in calls))
  saved=json.loads((job/'take-1-audit.json').read_text(encoding='utf8'))
  self.assertEqual(saved['acceptance'],['James leaves'])
 def test_silent_beat_skips_audio_check(self):
  job=self._job();beat_value=beat()
  def run(args,**kwargs):return type('r',(),{'stdout':b''})()
  with patch.object(D.P,'extract_tail'),patch.object(D.P,'audio_vector') as vector:
   out=D.audit_take(job/'take-1.mp4',beat_value,job,None,run=run)
  self.assertNotIn('audio',out);vector.assert_not_called()

def _fixture(root):
 tmp=Path(root)
 job=tmp/'job';job.mkdir();source=tmp/'src';(source/'segments').mkdir(parents=True)
 (source/'state.json').write_text(json.dumps({'segments':{'shot-01-01':{'graph':template()}}}),encoding='utf8')
 (source/'request.json').write_text(json.dumps({'fps':24,'width':1280,'height':720,'show_path':str(tmp/'series'/'sig')}),encoding='utf8')
 return job,source

def _api_for(job,source):
 def api(path,payload=None):
  if path=='/queue':return {'queue_running':[],'queue_pending':[]}
  if path=='/prompt':
   out=source.parent;target=job/'rendered.mp4';target.write_bytes(b'mp4');(job/'gate').write_text(json.dumps({'decision':'approve','evidence':['ok']}),encoding='utf8');return {}
  if path=='/interrupt':raise AssertionError('interrupt must not be used on success')
  raise AssertionError('unexpected endpoint '+path)
 return api

class OrchestratorTests(unittest.TestCase):
 def _patch_lifecycle(self):
  # Managed mode owns GPU hardware: stub the process-level operations so tests exercise
  # the lifecycle (queue idle check, Strata kill, free, guaranteed verified restore) with zero real side effects.
  # If the caller already mocked an attribute (e.g. an external probe whose counters must see the
  # calls), keep that mock active instead of shadowing it with a private one.
  if not isinstance(D.subprocess.run,Mock):
   p=patch.object(D.subprocess,'run');self.proc=p.start();self.proc.return_value=type('r',(),{'returncode':0})();self.addCleanup(p.stop)
  else:self.proc=D.subprocess.run
  if not isinstance(D.P.locked,Mock):
   lock=patch.object(D.P,'locked');self.lock=lock.start();self.lock.side_effect=lambda *a,**k:contextlib.nullcontext();self.addCleanup(lock.stop)
  else:self.lock=D.P.locked
  if not isinstance(D.P.OPENER,Mock):
   opener=patch.object(D.P,'OPENER');self.opener=opener.start();self.addCleanup(opener.stop)
  if not isinstance(D.time,SimpleNamespace):
   tm=patch.object(D,'time',new=SimpleNamespace(sleep=lambda s:None,monotonic=time.monotonic,strftime=time.strftime));tm.start();self.addCleanup(tm.stop)
 def _run(self,mode,overrides=None,gates=None,plan_overrides=None,expect_error=None,reuse=None,api=None,beats_list=None,proc_returns=None):
  if reuse:tmp,job=reuse;source_path=job.parent/'src'
  else:
   tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);job,source=_fixture(tmp.name);source_path=source
  self._patch_lifecycle()
  if proc_returns:self.proc.side_effect=[type('r',(),{'returncode':code})() for code in proc_returns]
  beats=[beat()] if beats_list is None else beats_list
  if overrides:beats[0].update(overrides)
  raw=plan(beats=beats,source_job=str(source_path),**(plan_overrides or {}))
  plan_path=Path(tmp.name)/'plan.json';plan_path.write_text(json.dumps(raw),encoding='utf8')
  gates=gates or [{'decision':'approve','evidence':['ok']}]
  state={'n':0}
  def gate(beat_value,record):
   decision=gates[min(state['n'],len(gates)-1)];state['n']+=1
   if decision is None:raise D.DirectiveError('gate called beyond provided reviews')
   return decision
  api_calls=[]
  def default_api(path,payload=None):
   api_calls.append(path)
   if path=='/queue':return {'queue_running':[],'queue_pending':[]}
   if path=='/prompt':(job/'rendered.mp4').write_bytes(b'mp4');return {}
   return {}
  use_api=api or default_api
  def locate(prompt_id):
   return 'history',{'status':{'status_str':'success'},'outputs':{'136':{'videos':[{'filename':'out.mp4','subfolder':''}]}}}
  with patch.object(D.C,'load_show',return_value=SHOW),patch.object(D.C,'load_cast',return_value=CAST),\
   patch.object(D,'submit_take') as submit,patch.object(D,'audit_take',return_value={'tail':'tail.png'}),\
   patch.object(D.P,'duration',return_value=5.166667),patch.object(D,'sha256',return_value='0'*64):
   submit.side_effect=lambda plan_value,record,*a,**k:(record.update(output=str(job/'rendered.mp4')),record)[1]
   if mode=='managed':
    try:
     result=D.run_directive(plan_path,job,mode='managed',gate=gate,assemble=lambda j,s:(j/'assembled.mp4'),api=use_api,locate=locate,log=lambda *a:None)
    except D.DirectiveError as error:
     if not expect_error:raise
     self.assertIn(expect_error,str(error));result={'error':str(error)}
   else:
    def boom(*a,**k):raise AssertionError('dry run touched the GPU api')
    result=D.run_directive(plan_path,job,mode='dry',api=boom,log=lambda *a:None)
  return tmp,job,result,submit

 def test_dry_run_builds_without_gpu_or_ledger_commit(self):
  tmp,job,result,submit=self._run('dry')
  submit.assert_not_called()
  planned=json.loads((job/'directive-plan.json').read_text(encoding='utf8'))
  self.assertEqual(planned['takes'],['t-exit-take1'])
  self.assertFalse((job/'story_state.json').exists())
  self.assertIn('zero calls',json.dumps(planned['commitments']))
 def test_approve_commits_ledger_advances_guide_and_assembles(self):
  tmp,job,result,submit=self._run('managed')
  ledger=json.loads((job/'story_state.json').read_text(encoding='utf8'))
  self.assertEqual(ledger['entries'][0]['decision'],'approve');self.assertEqual(ledger['entries'][0]['after']['james'],'missing_offscreen')
  self.assertEqual(result['output'],str(job/'assembled.mp4'))
  second=job/'t-exit-take2.json'
  self.assertFalse(second.exists())
  result_json=json.loads((job/'result.json').read_text(encoding='utf8'))
  self.assertEqual(result_json['status'],'awaiting_owner_playback')
  self.assertIn('rendered.mp4',result_json['inputs_sha256'])
  with self.assertRaisesRegex(D.DirectiveError,'committed story state'):self._run_managed_stale(tmp,job)
 def _run_managed_stale(self,tmp,job):
  # After the approved exit the committed state has James gone; a plan still asking
  # to render him on screen without re-entry must be refused.
  source=Path(tmp.name)/'src'
  stale=plan(beats=[beat(id='again',before={'james':'inside','kate':'inside'},after={'james':'inside','kate':'inside'})],source_job=str(source))
  # normalize: first validate already fails because initial_state matches ledger initial; bypass validate by calling plan_take directly
  plan_value=D.normalize_plan(stale);plan_value['_template']=template()
  ledger=D.StoryLedger.load(job/'story_state.json',plan_value['initial_state'])
  D.plan_take(plan_value,plan_value['beats'][0],SHOW,CAST,ledger.state,None,1)
 def test_retry_uses_budget_with_correction(self):
  tmp,job,result,submit=self._run('managed',gates=[{'decision':'retry','correction':'lock the camera','reason':'extra man'},{'decision':'approve','evidence':['ok']}])
  ledger=json.loads((job/'story_state.json').read_text(encoding='utf8'))
  self.assertEqual([e['decision'] for e in ledger['entries']],['retry','approve'])
  self.assertEqual(ledger['entries'][0]['correction'],'lock the camera')
  calls=[call.args[1] for call in submit.call_args_list]
  self.assertEqual(calls[0]['correction'],'');self.assertEqual(calls[1]['correction'],'lock the camera')
 def test_second_retry_and_reject_abort_without_downstream_beats(self):
  tmp,job,result,submit=self._run('managed',gates=[{'decision':'retry','correction':'fix','reason':'x'},{'decision':'retry','correction':'fix2','reason':'y'}],expect_error='downstream beats were not rendered')
  self.assertIn('story acceptance failed at exit',result['error'])
  self.assertFalse((job/'result.json').exists())
  ledger=json.loads((job/'story_state.json').read_text(encoding='utf8'))
  self.assertEqual(ledger['entries'][-1]['decision'],'reject')
  self.assertEqual(len(submit.call_args_list),2)
 def test_output_never_overwritten(self):
  tmp,job,result,submit=self._run('dry')
  existing=job/'t-exit-take1.mp4';existing.write_bytes(b'approved')
  with patch.object(D.C,'load_show',return_value=SHOW),patch.object(D.C,'load_cast',return_value=CAST),patch.object(D,'audit_take',return_value={'tail':'tail.png'}):
   record={'take_name':'t-exit-take1','graph':template(),'guide':None,'audio':'silence','on_screen_cast':[]}
   with self.assertRaisesRegex(D.DirectiveError,'not overwritten'):
    D.submit_take({'id':'t'},record,SHOW,CAST,job,api=lambda *a,**k:(_ for _ in ()).throw(AssertionError('api touched')))
  self.assertEqual(existing.read_bytes(),b'approved')

 def test_managed_lifecycle_locks_queue_check_kill_and_verified_restore(self):
  tmp,job,result,submit=self._run('managed')
  self.assertEqual([c.args[0].name for c in self.lock.call_args_list],['pipeline.lock','gpu.lock'])
  cmds=[' '.join(str(part) for part in c.args[0]) for c in self.proc.call_args_list]
  self.assertEqual(len(cmds),2)
  self.assertIn('kill-strata.ps1',cmds[0]);self.assertIn('run.ps1',cmds[1]);self.assertIn('-RestoreOnly',cmds[1])
  lifecycle=json.loads((job/'gpu-lifecycle.json').read_text(encoding='utf8'))
  self.assertEqual(lifecycle['restore_exit'],0);self.assertTrue(lifecycle['strata_restored'])
 def test_managed_restore_guaranteed_after_rejection(self):
  tmp,job,result,submit=self._run('managed',gates=[{'decision':'reject','reason':'identity drift'}],expect_error='downstream beats were not rendered')
  cmds=[' '.join(str(part) for part in c.args[0]) for c in self.proc.call_args_list]
  self.assertEqual(len(cmds),2);self.assertIn('-RestoreOnly',cmds[1])
  self.assertTrue((job/'gpu-restore.log').exists())
 def test_managed_restore_failure_surfaces(self):
  tmp,job,result,submit=self._run('managed',expect_error='Strata restoration failed',proc_returns=[0,1])
 def test_managed_refuses_busy_queue_before_touching_anything(self):
  def busy(path,payload=None):
   if path=='/queue':return {'queue_running':[[9,'someone-else']],'queue_pending':[]}
   raise AssertionError('no other endpoint may be touched while busy')
  tmp,job,result,submit=self._run('managed',api=busy,expect_error='refusing to take ownership')
  self.assertEqual(self.proc.call_count,0);submit.assert_not_called()
  self.assertFalse((job/'gpu-lifecycle.json').exists())
 def test_dry_mode_never_touches_gpu_ownership(self):
  tmp,job,result,submit=self._run('dry')
  self.assertEqual(self.proc.call_count,0);self.assertEqual(self.lock.call_count,0)
 def test_zero_retry_budget_rejects_without_second_render(self):
  tmp,job,result,submit=self._run('managed',gates=[{'decision':'retry','correction':'changed camera','reason':'framing'},{'decision':'approve','evidence':['ok']}],plan_overrides={'max_changed_retries':0},expect_error='changed-retry budget exhausted')
  self.assertEqual(len(submit.call_args_list),1)
  ledger=json.loads((job/'story_state.json').read_text(encoding='utf8'))
  self.assertEqual([e['decision'] for e in ledger['entries']],['reject'])
  self.assertIn('changed-retry budget exhausted',ledger['entries'][0]['reason'])
 def _seed_ledger(self,job,entries):P.atomic(job/'story_state.json',{'initial_state':{'james':'inside','kate':'inside'},'entries':entries})
 def test_resume_renders_only_next_unapproved_beat_with_restored_guide(self):
  first=beat()
  second=beat(id='pursuit',before={'james':'missing_offscreen','kate':'inside'},after={'james':'missing_offscreen','kate':'outside'},on_screen_cast=['kate'],action='Kate follows his tracks.')
  tmp,job,result,submit=self._run('dry',beats_list=[first,second])
  tail=job/'t-exit-take1-tail.png';tail.write_bytes(b'png');output=job/'t-exit-take1.mp4';output.write_bytes(b'mp4')
  self._seed_ledger(job,[{'beat':'exit','take':1,'take_name':'t-exit-take1','decision':'approve','after':first['after'],'output':str(output),'tail':str(tail),'cast_at_end':['james','kate'],'evidence':['ok']}])
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),beats_list=[first,second],gates=[{'decision':'approve','evidence':['ok']}])
  self.assertEqual(len(submit2.call_args_list),1)
  record=submit2.call_args_list[0].args[1]
  self.assertEqual(record['beat'],'pursuit');self.assertEqual(record['take'],1);self.assertEqual(record['guide'],str(tail))
  ledger=json.loads((job/'story_state.json').read_text(encoding='utf8'))
  self.assertEqual([e['beat'] for e in ledger['entries']],['exit','pursuit'])
  approved=json.loads((job/'result.json').read_text(encoding='utf8'))['beats']
  self.assertEqual([b['beat'] for b in approved],['exit','pursuit'])
 def test_finalize_only_after_all_beats_approved(self):
  tmp,job,result,submit=self._run('dry')
  tail=job/'t-exit-take1-tail.png';tail.write_bytes(b'png');output=job/'t-exit-take1.mp4';output.write_bytes(b'mp4')
  self._seed_ledger(job,[{'beat':'exit','take':1,'take_name':'t-exit-take1','decision':'approve','after':beat()['after'],'output':str(output),'tail':str(tail),'cast_at_end':['james','kate'],'evidence':['ok']}])
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),gates=[{'decision':'never-called'}])
  submit2.assert_not_called()
  result_json=json.loads((job/'result.json').read_text(encoding='utf8'))
  self.assertEqual(result_json['status'],'awaiting_owner_playback')
  self.assertIn('t-exit-take1.mp4',result_json['inputs_sha256'])
 def test_resume_refuses_plan_revision_after_approval(self):
  tmp,job,result,submit=self._run('dry')
  tail=job/'t-exit-take1-tail.png';tail.write_bytes(b'png');output=job/'t-exit-take1.mp4';output.write_bytes(b'mp4')
  self._seed_ledger(job,[{'beat':'exit','take':1,'take_name':'t-exit-take1','decision':'approve','after':beat()['after'],'output':str(output),'tail':str(tail),'cast_at_end':['james','kate'],'evidence':['ok']}])
  revised=beat(after={'james':'missing_at_tree_line','kate':'inside'})
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),beats_list=[revised],expect_error='does not match this plan revision')
  submit2.assert_not_called()
 def test_resume_after_recorded_retry_resumes_with_persisted_correction(self):
  tmp,job,result,submit=self._run('dry')
  self._seed_ledger(job,[{'beat':'exit','take':1,'decision':'retry','correction':'lock the camera','reason':'extra man'}])
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),gates=[{'decision':'approve','evidence':['ok']}])
  record=submit2.call_args_list[0].args[1]
  self.assertEqual((record['take'],record['correction']),(2,'lock the camera'))
 def test_resume_after_recorded_retry_enforces_exhausted_budget(self):
  tmp,job,result,submit=self._run('dry')
  self._seed_ledger(job,[{'beat':'exit','take':1,'decision':'retry','correction':'lock the camera','reason':'extra man'}])
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),gates=[{'decision':'retry','correction':'again','reason':'still wrong'}],expect_error='changed-retry budget exhausted')
  self.assertEqual(len(submit2.call_args_list),1)
 def test_resume_refuses_prior_rejection(self):
  tmp,job,result,submit=self._run('dry')
  self._seed_ledger(job,[{'beat':'exit','take':1,'decision':'reject','reason':'identity drift'}])
  tmp2,job2,result2,submit2=self._run('managed',reuse=(tmp,job),gates=[{'decision':'never-called'}],expect_error='was rejected')
  submit2.assert_not_called()

class SubmitGuardTests(unittest.TestCase):
 def test_queue_busy_refuses_before_any_mutation(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp)
   record={'take_name':'t-x-take1','graph':template(),'guide':None,'audio':'silence','on_screen_cast':[]}
   def api(path,payload=None):
    if path=='/queue':return {'queue_running':[[1,'other']],'queue_pending':[]}
    raise AssertionError('submit after busy check')
   with self.assertRaisesRegex(D.DirectiveError,'queue occupied'):
    D.submit_take({'id':'t'},record,SHOW,CAST,job,api=api)
   self.assertFalse((job/'t-x-take1.json').exists())
 def test_timeout_interrupts_only_own_prompt(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp)
   record={'take_name':'t-x-take1','graph':template(),'guide':None,'audio':'silence','on_screen_cast':[],'dialogue_wav':None}
   calls=[];sent=[]
   def api(path,payload=None):
    calls.append(path)
    if path=='/queue':return {'queue_running':[[0,sent[0]]] if sent else [],'queue_pending':[]}
    if path=='/prompt':sent.append(payload['prompt_id']);return {}
    if path=='/interrupt':return {}
    raise AssertionError(path)
   times=iter([0,0,30,30,999,999])
   with patch.object(D,'silence_wav',return_value=Path('silence.wav')):
    with self.assertRaisesRegex(D.DirectiveError,'timed out'):
     D.submit_take({'id':'t'},record,SHOW,CAST,job,api=api,locate=lambda pid:('running',None),clock=lambda:next(times),sleep=lambda s:None,timeout_s=30)
   self.assertIn('/interrupt',calls)
   self.assertEqual(calls.count('/prompt'),1)
   status=json.loads((job/'t-x-take1.json').read_text(encoding='utf8'))['status']
   self.assertEqual(status,'submitted')

class SubmitReconcileTests(unittest.TestCase):
 def test_existing_submitted_prompt_is_reconciled_not_resubmitted(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);name='existing-take'
   record={'take_name':name,'graph':template(),'guide':None,'audio':'silence','on_screen_cast':[]}
   D.P.atomic(job/(name+'.json'),{'status':'submitted','prompt_id':'original-prompt-id'})
   sent=[]
   def api(path,payload=None):
    if path=='/prompt':sent.append(payload['prompt_id']);return {}
    raise AssertionError('no endpoint may be touched during reconcile: '+path)
   with patch.object(D,'silence_wav') as silence,patch.object(D.shutil,'copy2') as copy:
    out=D.submit_take({'id':'t'},record,SHOW,CAST,job,api=api,locate=lambda pid:('history',{'status':{'status_str':'success'},'outputs':{'136':{'gifs':[{'filename':'fake.mp4'}]}}}),clock=lambda:0,sleep=lambda s:None)
   self.assertEqual(sent,[]);silence.assert_not_called()
   self.assertEqual(copy.call_args.args[1],job/(name+'.mp4'))
   self.assertEqual(out['prompt_id'],'original-prompt-id')
   persisted=json.loads((job/(name+'.json')).read_text(encoding='utf8'))
   self.assertEqual((persisted['prompt_id'],persisted['status']),('original-prompt-id','complete'))
 def test_existing_failed_prompt_refuses_without_new_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);name='existing-take'
   record={'take_name':name,'graph':template(),'guide':None,'audio':'silence','on_screen_cast':[]}
   D.P.atomic(job/(name+'.json'),{'status':'submitted','prompt_id':'original-prompt-id'})
   def api(path,payload=None):raise AssertionError('no endpoint: '+path)
   with self.assertRaisesRegex(D.DirectiveError,'Render failed'):
    D.submit_take({'id':'t'},record,SHOW,CAST,job,api=api,locate=lambda pid:('history',{'status':{'status_str':'error'}}),clock=lambda:0,sleep=lambda s:None)
   persisted=json.loads((job/(name+'.json')).read_text(encoding='utf8'))
   self.assertEqual((persisted['prompt_id'],persisted['status']),('original-prompt-id','failed'))
 def test_take_record_without_prompt_id_refuses_ambiguous_outcome(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);name='existing-take'
   record={'take_name':name,'graph':template(),'guide':None,'audio':'silence','on_screen_cast':[]}
   D.P.atomic(job/(name+'.json'),{'status':'submitting'})
   def api(path,payload=None):raise AssertionError('no endpoint may confirm an ambiguous outcome: '+path)
   with self.assertRaisesRegex(D.DirectiveError,'without a prompt_id'):
    D.submit_take({'id':'t'},record,SHOW,CAST,job,api=api,locate=lambda pid:('unknown',None),clock=lambda:0,sleep=lambda s:None)

class LifecycleIsolationRegressionTests(unittest.TestCase):
 def test_default_process_runner_respects_runtime_mock(self):
  # A mock bypass must fail safely instead of executing the real shutdown script.
  with patch.object(D.subprocess,'run') as run,patch.object(D.subprocess,'Popen',side_effect=AssertionError('real process escaped the mock')),patch.object(D.P,'locked',side_effect=lambda *a,**k:contextlib.nullcontext()),patch.object(D.P,'OPENER'):
   run.return_value=SimpleNamespace(returncode=0)
   with D.gpu_session(api=lambda *a,**k:{'queue_running':[],'queue_pending':[]},sleep=lambda s:None,log=lambda *a:None):pass
  self.assertEqual(run.call_count,2)
  self.assertIn('kill-strata.ps1',str(run.call_args_list[0]))
  self.assertIn('-RestoreOnly',str(run.call_args_list[1]))

 def test_memory_release_failure_still_restores_strata(self):
  with patch.object(D.P,'locked',side_effect=lambda *a,**k:contextlib.nullcontext()),patch.object(D.P,'OPENER') as opener:
   opener.open.side_effect=RuntimeError('memory release failed')
   run=unittest.mock.Mock(return_value=SimpleNamespace(returncode=0))
   with self.assertRaisesRegex(RuntimeError,'memory release failed'):
    with D.gpu_session(api=lambda *a,**k:{'queue_running':[],'queue_pending':[]},run=run,sleep=lambda s:None,log=lambda *a:None):pass
  self.assertEqual(run.call_count,2)
  self.assertIn('-RestoreOnly',str(run.call_args_list[1]))

if __name__=='__main__':unittest.main()
