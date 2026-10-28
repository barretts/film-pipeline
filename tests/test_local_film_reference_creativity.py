import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline

class StopBeforeRender(Exception):pass

class ReferenceCreativityTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.base=self.root/'comfy';(self.base/'input').mkdir(parents=True)
  pipeline.atomic(self.base/'ref2va-audio-comparison-graph.json',pipeline.load(pipeline.BASE/'ref2va-audio-comparison-graph.json'))
  self.audio=self.root/'voice.wav';self.audio.write_bytes(b'fixture');self.image=self.root/'reference.png';self.image.write_bytes(b'fixture');self.counter=0
 def tearDown(self):self.temp.cleanup()
 def graph(self,value=None,index=0,obj=False,has_ref=True):
  self.counter+=1;job=self.root/str(self.counter);job.mkdir();state={'job_id':'fixture','segments':{},'events':[]}
  req={'width':1080,'height':1920,'style':'documentary','segment_instructions':'Camera stays static.','staged_references':[{'path':str(self.image)}] if has_ref else []}
  if value is not None:req['reference_creativity']=value
  if obj:req['staged_object_reference']={'path':str(self.image)}
  shot={'id':'shot-01','voice':str(self.audio),'character':'An adult woman','scene':'A room','action':'Speaks to viewer','prompt':'At a desk','continuation_action':'Continues speaking'}
  with patch.object(pipeline,'BASE',self.base),patch.object(pipeline,'wait_idle',side_effect=StopBeforeRender):
   with self.assertRaises(StopBeforeRender):pipeline.render_segment(job,state,shot,index,self.image if has_ref else None,req)
  return state['segments'][f'shot-01-{index:02}']['graph']
 def test_default_and_explicit_zero_keep_identical_graphs(self):
  self.assertEqual(self.graph(),self.graph(0))
  self.assertEqual(self.graph(obj=True),self.graph(0,obj=True))
 def test_positive_creativity_uses_character_reference_without_fixed_frame(self):
  graph=self.graph(25);node=graph['157'];self.assertEqual(node['class_type'],'MiniMaxH3ReferenceToVideo');self.assertEqual(node['inputs']['ref_images.ref_image_0'],['5',0]);self.assertNotIn('first_frame',node['inputs']);self.assertIn('25/100',node['inputs']['prompt']);self.assertNotIn('exact face, hair, clothing',node['inputs']['prompt']);self.assertTrue(node['inputs']['prompt'].endswith('Camera stays static.'));self.assertEqual(graph['19']['inputs']['positive'],['160',0])
 def test_character_and_object_references_keep_distinct_roles(self):
  node=self.graph(80,obj=True)['157'];self.assertEqual(node['inputs']['ref_images.ref_image_1'],['161',0]);self.assertIn('<Picture 1> as the character',node['inputs']['prompt']);self.assertIn('<Picture 2> as the visual reference',node['inputs']['prompt'])
 def test_high_creativity_does_not_change_continuation_path(self):
  self.assertEqual(self.graph(0,index=1,obj=True),self.graph(90,index=1,obj=True))
 def test_without_character_reference_creativity_has_no_effect(self):
  self.assertEqual(self.graph(0,has_ref=False,obj=True),self.graph(90,has_ref=False,obj=True))
 def test_invalid_values_rejected_at_request_boundary(self):
  req={'brief':'A demo','script':'Hello there.','style':'realistic'}
  for value in (-1,101,True,None,'50',float('nan'),float('inf')):
   with self.subTest(value=value),self.assertRaises(pipeline.JobError):pipeline.validate(dict(req,reference_creativity=value))
 def test_planner_receives_the_saved_creativity(self):
  job=self.root/'plan';job.mkdir();pipeline.atomic(job/'request.json',{'brief':'An adult presenter','script':'Hello there.','style':'documentary','staged_references':[{'path':str(self.image)}],'reference_creativity':75})
  state={'events':[]};answer={'character':'A referenced adult','shots':[{'scene':'A room','action':'Speaks','prompt':'A presenter','continuation_action':'Keeps speaking'}]}
  with patch.object(pipeline.planner,'plan',return_value=answer) as planner:pipeline.make_plan(job,state)
  self.assertEqual(planner.call_args.kwargs['reference_creativity'],75);self.assertTrue(planner.call_args.kwargs['has_reference'])

if __name__=='__main__':unittest.main()
