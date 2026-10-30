import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import writer
from local_film.pipeline import JobError

class Response(io.BytesIO):
 status=200

def chat(content):return Response(json.dumps({'choices':[{'message':{'content':content}}]}).encode())

def script_payload(word='ok'):
 return {'title':'First Light','synopsis':'Two operators hear an impossible signal.','lines':[
  {'scene':'inside the radio hut','setting':'one amber lamp','action':'Alice leans closer to the receiver.','dialogue':[{'character':'alice','text':'Do you hear that? '+word}]},
  {'scene':'outside the hut','setting':'wind over the antenna field','action':'Bob points at the dish while Alice films.','dialogue':[{'character':'bob','text':'It is moving on its own.'}]},
  {'scene':'on the ice shelf','setting':'blue light under the ice','action':'They stand at the edge.','dialogue':[{'character':'alice','text':'We have to tell base.'}]}],
  'ending_state':'Alice steps out onto the ice with the portable receiver.','next_hook':'The signal answers.'}

show={'id':'polar-night','title':'Polar Night','logline':'Two radio operators decode a signal that should not exist.','brief':'Cold blue realism at a polar listening post.','style':'Cold blue-white cinematic realism, 35mm grain.','arc_summary':'Episode 1 ends outside.','characters':['alice','bob']}
cast={'alice':{'name':'Alice','description':'A composed radio operator.','appearance':'Navy wool jacket.'},'bob':{'name':'Bob','description':'A young glaciologist.','appearance':'Red parka.'}}

class WriterGenerateTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.log=Path(self._tmp.name)/'writer.jsonl'
  proc=patch.object(writer.subprocess,'Popen');mock=proc.start();mock.return_value.poll.return_value=None;self.addCleanup(proc.stop)
  server=patch.object(writer,'_server',return_value=(1234,['cmd']));server.start();self.addCleanup(server.stop)
 def tearDown(self):self._tmp.cleanup()
 def drive(self,responses,**over):
  openings=[]
  def fake_open(request,timeout=2):
   if isinstance(request,str)and request.endswith('/health'):return Response(b'ok')
   openings.append(request)
   result=responses[min(len(openings)-1,len(responses)-1)]
   return result() if callable(result) else result
  opener=patch.object(writer,'OPENER');mock=opener.start();mock.open.side_effect=fake_open;self.addCleanup(opener.stop)
  return writer._generate(1234,['cmd'],'system','user',{'type':'object'},'episode_script',self.log,over.get('validate',lambda d:True))
 def test_first_valid_answer_returned(self):
  answer=self.drive([lambda:chat(json.dumps({'ok':True}))])
  self.assertEqual(answer,{'ok':True})
  events=[json.loads(x) for x in self.log.read_text(encoding='utf8').splitlines()]
  self.assertEqual(events[0]['event'],'response')
 def test_correction_then_success(self):
  answer=self.drive([lambda:chat('not json'),lambda:chat(json.dumps({'ok':2}))],validate=lambda d:d.get('ok')==2)
  self.assertEqual(answer,{'ok':2})
  events=[json.loads(x) for x in self.log.read_text(encoding='utf8').splitlines()]
  self.assertEqual([e['attempt']for e in events],[0,1])
 def test_gives_up_after_two_corrections(self):
  with self.assertRaisesRegex(JobError,'after two corrections'):self.drive([lambda:chat('nope')])
 def test_none_log_path_tolerated(self):
  opener=patch.object(writer,'OPENER');mock=opener.start();self.addCleanup(opener.stop)
  mock.open.side_effect=lambda request,timeout=2:Response(b'ok')if isinstance(request,str)else chat(json.dumps({'ok':True}))
  self.assertEqual(writer._generate(1,'c','s','u',{},'n',None,lambda d:True),{'ok':True})

class WriterValidatorsTests(unittest.TestCase):
 def capture_validate(self,fn,*args):
  seen={}
  def fake_generate(port,command,system,user,schema,name,log_path,validate,max_tokens=3000):
   seen['validate']=validate;seen['system']=system;seen['user']=user;seen['name']=name;return {'captured':True}
  with patch.object(writer,'_server',return_value=(1,['c'])),patch.object(writer,'_generate',side_effect=fake_generate):self.assertEqual(fn(*args),{'captured':True})
  return seen
 def test_draft_cast_slug_and_count_rules(self):
  seen=self.capture_validate(writer.draft_cast,show,'a series brief for the polar post',3,Path('/tmp/unused.jsonl'))
  good={'recurring':[{'slug':'alice','name':'Alice','role':'operator'},{'slug':'bob-2','name':'Bob','role':'glaciologist'}],'episode':[{'number':n,'name':'N','role':'r'}for n in (1,2,3)]}
  self.assertTrue(seen['validate'](good))
  bad=[dict(good,recurring=[{'slug':'Alice','name':'A','role':'r'},{'slug':'bob','name':'B','role':'r'}]),
   dict(good,recurring=[{'slug':'alice','name':'A','role':'r'}]),
   dict(good,recurring=[{'slug':'alice','name':'A','role':'r'},{'slug':'alice','name':'B','role':'r'}]),
   dict(good,episode=good['episode'][:2])]
  for value in bad:self.assertFalse(seen['validate'](value),value)
  self.assertIn('polar post',seen['user'])
 def test_draft_arc_requires_substantial_briefs(self):
  seen=self.capture_validate(writer.draft_arc,show,cast,'a polar listening post arc brief',3,Path('/tmp/unused.jsonl'))
  good={'episodes':[{'number':n,'brief':'The post hears a new anomaly and one operator moves further out onto the ice.','ending_note':'closer'}for n in (1,2,3)]}
  self.assertTrue(seen['validate'](good))
  self.assertFalse(seen['validate']({'episodes':[{'number':1,'brief':'short','ending_note':'x'}]}))
  self.assertFalse(seen['validate']({'episodes':[{'number':1,'brief':'x'*40,'ending_note':''}]}))
  self.assertIn('Episode 1 ends outside',seen['user'])
 def test_draft_script_word_budget_and_membership(self):
  seen=self.capture_validate(writer.draft_script,show,cast,'ARC','prev-hooked','ep brief',40,Path('/tmp/unused.jsonl'))
  self.assertIn('prev-hooked',seen['system'])
  self.assertTrue(seen['validate'](script_payload()))
  self.assertFalse(seen['validate'](dict(script_payload(),lines=[dict(line,dialogue=[{'character':'alice','text':'word '*50}])for line in script_payload()['lines']])))
  self.assertFalse(seen['validate'](dict(script_payload(),lines=script_payload()['lines'][:2])))
  alien=script_payload();alien['lines'][0]['dialogue']=[{'character':'carl','text':'x'}]
  self.assertFalse(seen['validate'](alien))
  self.assertFalse(seen['validate'](dict(script_payload(),ending_state='')))
 def test_over_budget_real_generate_records_correction(self):
  fat=dict(script_payload(),lines=[dict(line,dialogue=[{'character':'alice','text':'word '*50}])for line in script_payload()['lines']])
  class Opener:
   def __init__(self):self.n=0
   def open(self,request,timeout=2):
    if isinstance(request,str):return Response(b'ok')
    self.n+=1
    return chat(json.dumps(fat if self.n==1 else script_payload()))
  with tempfile.TemporaryDirectory() as tmp,patch.object(writer,'_server',return_value=(1,['c'])),patch.object(writer.subprocess,'Popen')as popen,patch.object(writer,'OPENER',Opener()):
   popen.return_value.poll.return_value=None
   log=Path(tmp)/'w.jsonl';result=writer.draft_script(show,cast,'ARC','prev-hooked','ep brief',40,log)
   events=[json.loads(x)for x in log.read_text(encoding='utf8').splitlines()]
  self.assertEqual(result['title'],'First Light')
  self.assertEqual(events[0]['attempt'],0);self.assertEqual(events[1]['attempt'],1)

class StoryboardTests(unittest.TestCase):
 def test_storyboard_builds_episode_shots(self):
  episode=writer.storyboard(show,cast,script_payload(),None,number=2,target_seconds=90,episode_id='02-the-answer')
  self.assertEqual(episode['id'],'02-the-answer');self.assertEqual(episode['number'],2);self.assertEqual(episode['target_seconds'],90)
  self.assertEqual(episode['ending_state'],'Alice steps out onto the ice with the portable receiver.')
  shots=episode['shots']
  self.assertEqual([s['id']for s in shots],['shot-01','shot-02','shot-03'])
  self.assertEqual(shots[0]['characters'],['alice'])
  self.assertEqual(shots[0]['speakers'],['alice'])
  self.assertEqual(shots[1]['characters'],['alice','bob'])
  self.assertEqual(shots[1]['speakers'],['bob'])
  self.assertTrue(shots[0]['prompt'].startswith('one amber lamp. Medium shot, locked camera. Alice:'))
  self.assertIn('Visual style: Cold blue-white cinematic realism',shots[0]['prompt'])
  self.assertIn('Bob points at the dish',shots[1]['prompt'])
  self.assertIn('Carry the moment forward toward: Bob points at the dish',shots[0]['continuation_action'])
  self.assertIn("Reach the episode's final position: Alice steps out",shots[2]['continuation_action'])
  self.assertEqual(shots[0]['dialogue'],[{'character':'alice','text':'Do you hear that? ok'}])
  self.assertEqual(shots[2]['speakers'],['alice'])
 def test_storyboard_default_id_from_number(self):
  episode=writer.storyboard(show,cast,script_payload(),None,number=3,target_seconds=60)
  self.assertEqual(episode['id'],'03-episode')

if __name__=='__main__':unittest.main()
