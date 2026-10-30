import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import characters,pipeline,series

def touch(path):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x89PNG fake');return path

def build_tree(root):
 alice={'id':'alice','name':'Alice','description':'A composed radio operator who trusts instruments more than rumors.','appearance':'Short grey hair, olive skin, always a navy wool jacket.','voice_model':'en_US-amy-medium.onnx','voice_sample':'audition-amy.wav','portrait':'portrait.png','ref_images':['portrait.png','refs/turn-01.png']}
 bob={'id':'bob','name':'Bob','description':'A young glaciologist who maps the ice on foot every clear morning.','appearance':'Red parka, frost on the hood, close cropped hair.','voice_model':'en_US-amy-medium.onnx','voice_sample':'audition-amy.wav','portrait':'portrait.png','ref_images':['portrait.png','refs/turn-01.png']}
 for slug,character in (('alice',alice),('bob',bob)):
  base=Path(root)/'characters'/slug;base.mkdir(parents=True)
  touch(base/'audition-amy.wav');touch(base/'portrait.png');touch(base/'refs/turn-01.png')
  (base/'character.json').write_text(json.dumps(character),encoding='utf8')
 show={'id':'polar-night','title':'Polar Night','logline':'Two radio operators decode a signal that should not exist.','brief':'Cold blue realism.','style':'Cold blue-white cinematic realism, 35mm grain.','arc_summary':'Episode 1 ends at the ice shelf.','width':1280,'height':720,'fps':24,'characters':['alice','bob']}
 (Path(root)/'polar-night').mkdir();(Path(root)/'polar-night/show.json').write_text(json.dumps(show),encoding='utf8')
 return characters.load_show(root,'polar-night'),characters.load_cast(root,show)

def base_graph():
 return {'5':{'class_type':'LoadImage','inputs':{}},'142':{'class_type':'ImageResizeKJv2','inputs':{}},
  '157':{'class_type':'MiniMaxH3DistilledImageToVideo','inputs':{}},'18':{'class_type':'LoadAudio','inputs':{}},
  '19':{'class_type':'LCH3AudioSync','inputs':{}},'130':{'class_type':'RandomNoise','inputs':{}},'136':{'class_type':'VHS_VideoCombine','inputs':{}}}

class SeriesPromptTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name);self.show,self.cast=build_tree(self.root)
 def tearDown(self):self._tmp.cleanup()
 def plan_with(self,shot):return {'shots':[shot]}
 def test_six_sections_exact_order_and_binding(self):
  shot={'id':'shot-01','scene':'inside the radio hut at night','action':'Alice warns Bob to step back.','continuation_action':'Bob lowers the binoculars.',
   'prompt':'unused','characters':['bob','alice'],'speakers':['alice','bob'],'dialogue':[{'character':'alice','text':'Do not move.'},{'character':'bob','text':'It is moving on its own.'}]}
  series.build_prompts(self.plan_with(shot),self.show,self.cast);prompt=shot['series_prompt']
  for header in('subject_definitions:','summary: [reference generation]','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:'):
   self.assertIn(header,prompt)
  self.assertLess(prompt.index('subject_definitions:'),prompt.index('summary:'))
  self.assertLess(prompt.index('summary:'),prompt.index('retention_analysis:'))
  self.assertLess(prompt.index('retention_analysis:'),prompt.index('detailed_description:'))
  self.assertLess(prompt.index('detailed_description:'),prompt.index('overall_soundscape:'))
  self.assertLess(prompt.index('overall_soundscape:'),prompt.index('non_diegetic_music:'))
  self.assertIn('<Subject 1> is the Alice whose appearance comes from <Picture 1>',prompt)
  self.assertIn('<Subject 2> is the Bob whose appearance comes from <Picture 2>',prompt)
  self.assertIn('The target video follows <Subject 1> and <Subject 2>.',prompt)
  self.assertIn('fully_preserved - the face, hair and clothing of <Subject 1> are retained',prompt)
  self.assertLess(prompt.index('Cold blue-white cinematic realism'),prompt.index('[Shot 1]'))
  self.assertIn('[Shot 1] inside the radio hut at night.',prompt)
  self.assertLess(prompt.index('Alice (S1) says <d>[English] Do not move. </d>'),prompt.index('Bob (S2) says <d>[English] It is moving on its own. </d>'))
  self.assertTrue(prompt.endswith(' The characters speak the supplied recordings naturally with precise lip movement.'))
  self.assertIn('overall_soundscape: minimal room tone.',prompt)
  self.assertIn('non_diegetic_music: restrained strings bed',prompt)
  self.assertEqual([shot['series_refs'][0],shot['series_refs'][1]],[str(Path(self.root)/'characters/alice/portrait.png'),str(Path(self.root)/'characters/bob/portrait.png')])
 def test_single_subject_phrasing(self):
  shot={'id':'shot-01','scene':'on the ice shelf','action':'Alice listens.','continuation_action':'She walks out.','prompt':'x','characters':['alice'],'speakers':[],'dialogue':[{'character':'alice','text':'<narration>'}]}
  series.build_prompts(self.plan_with(shot),self.show,self.cast)
  self.assertIn('The target video follows <Subject 1>.',shot['series_prompt'])
  self.assertIn('Alice (S1) says <d>[English] <narration> </d>',shot['series_prompt'])
 def test_continuation_prompt(self):
  shot={'id':'shot-02','scene':'outside the hut','action':'They argue.','continuation_action':'They walk toward the shelf.','prompt':'x','characters':['alice','bob'],'speakers':['bob'],'dialogue':[{'character':'bob','text':'We have to tell base.'}]}
  series.build_prompts(self.plan_with(shot),self.show,self.cast);continuation=shot['series_continuation']
  self.assertTrue(continuation.split('detailed_description:')[1].startswith(' Cold blue-white cinematic realism, 35mm grain.\n\nContinue seamlessly from the previous final frame.'))
  self.assertIn('Keep <Subject 1> and <Subject 2> in the same place, same clothing and identical appearance.',continuation)
  self.assertIn('They walk toward the shelf.',continuation)
  self.assertIn('Bob (S1) says <d>[English] We have to tell base. </d>',continuation)
 def test_show_soundscape_and_music_overrides(self):
  self.show['soundscape']='wind against the antenna mast';self.show['music']='low brass swells'
  shot={'id':'shot-01','scene':'s','action':'a','continuation_action':'c','prompt':'x','characters':['alice'],'speakers':[],'dialogue':[]}
  series.build_prompts(self.plan_with(shot),self.show,self.cast)
  self.assertIn('overall_soundscape: wind against the antenna mast',shot['series_prompt'])
  self.assertIn('non_diegetic_music: low brass swells',shot['series_prompt'])

class SeriesGraphTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.job=Path(self._tmp.name);(self.job/'input').mkdir();(self.job/'segments').mkdir()
  self.root=self.job/'series';self.show,self.cast=build_tree(self.root)
  shot={'id':'shot-01','voice':str(self.job/'v.wav'),'character':'Alice','scene':'inside the radio hut','action':'Alice listens.','prompt':'fallback'}
  portrait_a=str(Path(self.root)/'characters/alice/portrait.png');portrait_b=str(Path(self.root)/'characters/bob/portrait.png')
  shot.update(series_prompt='FIRST SERIES PROMPT',series_continuation='CONT SERIES PROMPT',series_refs=[portrait_a,portrait_b])
  self.shot=shot;self.req={'width':1280,'height':720,'style':'x','segment_frames':124,'continuation_overlap_frames':0}
 def tearDown(self):self._tmp.cleanup()
 def render(self,index=0,ref=None,shot=None,motion_ref=None):
  captured=[];state={'job_id':'test','segments':{}}
  def fake_api(path,payload):captured.append(payload['prompt']);return {}
  with patch.object(pipeline,'BASE',self.job),patch.object(pipeline,'load',side_effect=lambda path:base_graph()),patch.object(pipeline,'api',side_effect=fake_api),patch.object(pipeline,'locate',return_value=('unknown',None)),patch.object(pipeline,'wait_idle')as idle,patch.object(pipeline.shutil,'copyfile'):
   with self.assertRaisesRegex(pipeline.JobError,'lost job'):pipeline.render_segment(self.job,state,shot or self.shot,index,ref,self.req,motion_ref)
  return captured[0],idle
 def test_segment_zero_wires_reference_conditioning(self):
  graph,idle=self.render(0)
  self.assertEqual(graph['157']['class_type'],'MiniMaxH3ReferenceToVideo')
  self.assertEqual(graph['157']['inputs']['prompt'],'FIRST SERIES PROMPT')
  self.assertEqual(graph['157']['inputs']['ref_images.ref_image_0'],['170',0])
  self.assertEqual(graph['157']['inputs']['ref_images.ref_image_1'],['171',0])
  self.assertEqual(graph['170']['class_type'],'LoadImage');self.assertTrue(graph['170']['inputs']['image'].startswith('lf-test-cast-00'))
  self.assertEqual(graph['19']['inputs']['positive'],['160',0])
  self.assertNotIn('163',graph);self.assertNotIn('first_frame',graph['157']['inputs'])
  self.assertEqual(graph['19']['inputs']['start_seconds'],0.0)
  self.assertEqual(idle.call_args.args[1:],(self.job,7000))
 def test_continuation_anchors_tail_frame(self):
  tail=touch(self.job/'tail.mp4')
  graph,_=self.render(1,ref=str(tail))
  self.assertEqual(graph['157']['inputs']['prompt'],'CONT SERIES PROMPT')
  self.assertNotIn('first_frame',graph['157']['inputs'])
  self.assertEqual(graph['5']['inputs']['image'],'lf-test-shot-01-01.mp4')
  self.assertEqual(graph['163']['class_type'],'MiniMaxH3AddGuide')
  self.assertEqual(graph['163']['inputs'],{'positive':['160',0],'latent':['157',1],'vae':['11',0],'image':['142',0],'frame_idx':0})
  self.assertEqual(graph['19']['inputs']['positive'],['163',0])
 def test_single_video_path_untouched(self):
  shot={k:v for k,v in self.shot.items()if not k.startswith('series')}
  graph,idle=self.render(0,shot=shot)
  self.assertEqual(graph['157']['class_type'],'MiniMaxH3DistilledImageToVideo')
  self.assertNotIn('160',graph);self.assertNotIn('163',graph)
  self.assertIn('inside the radio hut',graph['157']['inputs']['prompt'])
  self.assertNotIn('ref_images.ref_image_0',graph['157']['inputs'])
  self.assertEqual(idle.call_args.args[1:],(self.job,12000))
  tail=touch(self.job/'tail2.mp4')
  graph,_=self.render(0,ref=str(tail),shot=dict(shot,id='shot-02'))
  self.assertEqual(graph['157']['inputs']['first_frame'],['142',0])
 def test_motion_guide_still_binds_after_reference(self):
  tail=touch(self.job/'tail3.mp4')
  graph,_=self.render(1,ref=str(tail),motion_ref=str(tail))
  self.assertEqual(graph['157']['class_type'],'MiniMaxH3ReferenceToVideo')
  self.assertEqual(graph['163']['inputs']['positive'],['157',0])
  self.assertEqual(graph['19']['inputs']['positive'],['163',0])
if __name__=='__main__':unittest.main()
