import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import characters,pipeline,series

def touch(path):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\x89PNG fake');return path

def build_tree(root):
 alice={'id':'alice','name':'Alice','description':'A composed radio operator who trusts instruments more than rumors.','appearance':'Short grey hair.','voice_model':'en_US-amy-medium.onnx','voice_sample':'audition-amy.wav','portrait':'portrait.png','ref_images':['portrait.png','refs/turn-01.png']}
 bob=dict(alice,id='bob',name='Bob',description='A young glaciologist who maps the ice on foot every clear morning.',appearance='Red parka.')
 for slug,character in (('alice',alice),('bob',bob)):
  base=Path(root)/'characters'/slug;base.mkdir(parents=True)
  touch(base/'audition-amy.wav');touch(base/'portrait.png');touch(base/'refs/turn-01.png')
  (base/'character.json').write_text(json.dumps(character),encoding='utf8')
 show={'id':'polar-night','title':'Polar Night','logline':'Two radio operators decode a signal that should not exist.','brief':'Cold blue realism.','style':'Cold blue-white cinematic realism, 35mm grain.','arc_summary':'Episode 1 ends at the ice shelf.','width':1280,'height':720,'fps':24,'characters':['alice','bob']}
 (Path(root)/'polar-night').mkdir();(Path(root)/'polar-night/show.json').write_text(json.dumps(show),encoding='utf8')
 return characters.load_show(root,'polar-night')

def make_episode(root,number=1,episode_id='01-first-light',shots=None,**overrides):
 episode={'id':episode_id,'number':number,'title':'First Light','target_seconds':90,'synopsis':'The first anomaly.','ending_state':'Alice steps out onto the ice.','next_hook':'The signal answers.','shots':shots if shots is not None else [{'id':'shot-01','scene':'inside the radio hut at night','setting':'one amber lamp','action':'Alice leans closer.','continuation_action':'She holds the headphones.','prompt':'Medium shot.','characters':['alice'],'speakers':['alice'],'dialogue':[{'character':'alice','text':'Do you hear that?'}]}]}
 episode.update(overrides);base=Path(root)/'polar-night/episodes'/episode_id;base.mkdir(parents=True,exist_ok=True)
 (base/'episode.json').write_text(json.dumps(episode),encoding='utf8');return episode

class SeriesCardTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name);self.show=build_tree(self.root);self.job=Path(self._tmp.name)/'job';self.job.mkdir()
  self.req={'series_root':str(self.root),'show':'polar-night','width':640,'height':360}
 def tearDown(self):self._tmp.cleanup()
 def test_card_segments_order_text_and_backgrounds(self):
  seen=[];final=touch(self.root/'polar-night/episodes/01-first-light/final-frame.png')
  def fake_build(job,name,text,background,width,height):
   seen.append((name,text,Path(background),width,height));path=Path(job)/'cards'/(name+'.mp4');touch(path);return path
  plan={'title':'First Light','next_hook':'The signal answers.\nMore text.','final_frame':str(final)}
  with patch.object(series,'build_card',side_effect=fake_build):
   out=series.card_segments(plan,self.job,self.req,self.show,{},[('seg-1',6.0),('seg-2',3.0)])
  self.assertEqual([p for p,_ in out],[out[0][0],'seg-1','seg-2',out[-1][0]])
  self.assertEqual([d for _,d in out],[2.0,6.0,3.0,2.0])
  self.assertEqual(seen[0][0],'title-card');self.assertEqual(seen[0][1],'Polar Night — First Light');self.assertEqual(seen[0][2],self.root/'polar-night/cards/title-bg.png')
  self.assertEqual(seen[1][0],'end-card');self.assertEqual(seen[1][1],'Next time: The signal answers.');self.assertEqual(seen[1][2],final)
  self.assertEqual(out[0][0],self.job/'cards'/'title-card.mp4');self.assertEqual(out[-1][0],self.job/'cards'/'end-card.mp4')
 def test_end_card_falls_back_to_show_end_background(self):
  seen=[]
  def fake_build(job,name,text,background,width,height):
   seen.append((name,text,Path(background)));path=Path(job)/'cards'/(name+'.mp4');touch(path);return path
  with patch.object(series,'build_card',side_effect=fake_build):series.card_segments({'title':'E'},self.job,self.req,self.show,{},[])
  self.assertEqual(seen[1][2],self.root/'polar-night/cards/title-bg.png')
  touch(self.root/'polar-night/cards/end-bg.png')
  seen.clear()
  with patch.object(series,'build_card',side_effect=fake_build):series.card_segments({'title':'E'},self.job,self.req,self.show,{},[])
  self.assertEqual(seen[1][2],self.root/'polar-night/cards/end-bg.png')
  hookless=[]
  def record(job,name,text,background,width,height):
   hookless.append(text);path=Path(job)/'cards'/(name+'.mp4');touch(path);return path
  with patch.object(series,'build_card',side_effect=record):series.card_segments({'title':'E','next_hook':'   '},self.job,self.req,self.show,{},[])
  self.assertEqual(hookless[1],'Polar Night — end')
 def test_build_card_renders_once_and_caches(self):
  calls=[]
  def fake_run(args,**kw):Path(args[-1]).write_bytes(b'mp4');calls.append(args)
  with patch.object(series,'run_cmd',side_effect=fake_run):
   first=series.build_card(self.job,'title-card','Polar Night — First Light',None,320,180)
   second=series.build_card(self.job,'title-card','Polar Night — First Light',None,320,180)
  self.assertEqual(first,second);self.assertTrue(first.is_file());self.assertEqual(len(calls),1)
  self.assertTrue((self.job/'cards'/'title-card.png').is_file())
  self.assertIn('-loop',calls[0]);self.assertIn('anullsrc=channel_layout=stereo:sample_rate=48000',calls[0])
 def test_build_card_cover_crops_supplied_background(self):
  from PIL import Image
  background=self.root/'bg.png';Image.new('RGB',(200,100),(10,20,30)).save(background)
  with patch.object(series,'run_cmd',side_effect=lambda args,**kw:Path(args[-1]).write_bytes(b'mp4')):series.build_card(self.job,'end-card','Next time: hook',str(background),160,120)
  from PIL import Image as I
  with I.open(self.job/'cards'/'end-card.png')as card:self.assertEqual(card.size,(160,120))

class SeriesContinuityTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name);self.show=build_tree(self.root)
  self.job=Path(self._tmp.name)/'job';(self.job/'review').mkdir(parents=True);touch(self.job/'review'/'assembled.mp4')
 def tearDown(self):self._tmp.cleanup()
 def test_save_continuity_records_final_frame_and_cast(self):
  episode_dir=self.root/'polar-night/episodes/02-the-answer';episode={'number':2,'next_hook':'Someone answers back.','shots':[{'characters':['alice','bob']},{'characters':['bob']}]}
  episode_dir.mkdir(parents=True)
  episode_path=episode_dir/'final-frame.png'
  with patch.object(series,'load',return_value=episode),patch.object(series,'extract_tail',side_effect=lambda video,target:target.write_bytes(b'PNG')),_patch_character():
   path=series.save_continuity(self.job,episode_dir,self.root/'polar-night','Alice walks toward the light.')
  data=json.loads(path.read_text(encoding='utf8'))
  self.assertEqual(data['number'],2);self.assertEqual(data['ending_state'],'Alice walks toward the light.');self.assertEqual(data['next_hook'],'Someone answers back.')
  self.assertEqual(Path(data['final_frame']).resolve(),episode_path.resolve());self.assertTrue(Path(data['final_frame']).is_file())
  self.assertEqual(list(data['cast_refs']),['alice','bob'])
  self.assertEqual(Path(data['cast_refs']['alice']).resolve(),(self.root/'characters/alice/portrait.png').resolve())
 def test_last_continuity_picks_highest_older_number(self):
  for name,number in (('01-first-light',1),('02-the-answer',2)):
   directory=self.root/'polar-night/episodes'/name;directory.mkdir(parents=True)
   (directory/'continuity.json').write_text(json.dumps({'number':number,'ending_state':'x','next_hook':'y','final_frame':'','cast_refs':{}}),encoding='utf8')
  self.assertEqual(series.last_continuity(self.root,'polar-night',3)['number'],2)
  self.assertEqual(series.last_continuity(self.root,'polar-night',2)['number'],1)
  self.assertEqual(series.last_continuity(self.root,'polar-night',1),{})
 def test_continuity_uses_final_scene_instead_of_end_card(self):
  episode_dir=self.root/'polar-night/episodes/01-first-light';episode_dir.mkdir(parents=True)
  scene=self.job/'segments'/'shot-01-00.mp4';touch(scene)
  episode={'number':1,'next_hook':'More follows.','shots':[{'characters':[]}]}
  with patch.object(series,'load',return_value=episode),patch.object(series,'extract_tail') as extract:
   series.save_continuity(self.job,episode_dir,self.root/'polar-night','The scene ends.',final_video=scene)
  extract.assert_called_once_with(scene,episode_dir/'final-frame.png')

class SeriesJobCreationTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name);self.show=build_tree(self.root);make_episode(self.root)
  self.jobs=Path(self._tmp.name)/'jobs'
 def tearDown(self):self._tmp.cleanup()
 def test_create_episode_request_and_resume_validation(self):
  with patch.object(pipeline,'JOBS',self.jobs):job=series.create_episode(self.root,'polar-night',1)
  self.assertTrue(job.parent==self.jobs)
  req=json.loads((job/'request.json').read_text(encoding='utf8'))
  self.assertEqual(req['kind'],'series');self.assertEqual(req['show'],'polar-night');self.assertEqual(req['episode'],'01-first-light')
  self.assertEqual(req['duration_seconds'],90);self.assertEqual(req['references'],[]);self.assertEqual(req['aspect'],'landscape')
  self.assertEqual(req['width'],1280);self.assertEqual(req['height'],720);self.assertEqual(req['fps'],24)
  self.assertEqual(req['show_path'],str(Path(self.show['_dir']).resolve()));self.assertEqual(req['episode_path'],str(Path(self.root/'polar-night/episodes/01-first-light').resolve()))
  self.assertEqual(req['seed_mode'],'random');self.assertIsInstance(req['seed'],int)
  again=pipeline.validate(json.loads((job/'request.json').read_text(encoding='utf8')))
  self.assertEqual(again['kind'],'series');self.assertEqual(again['style'],self.show['style'])
  self.assertEqual(pipeline.load(job/'state.json')['status'],'created')
 def test_create_episode_rejects_unknown_override(self):
  with patch.object(pipeline,'JOBS',self.jobs):
   with self.assertRaisesRegex(pipeline.JobError,'Unsupported series override'):series.create_episode(self.root,'polar-night',1,{'music':'x.mp3'})
   job=series.create_episode(self.root,'polar-night','01-first-light',{'duration_seconds':60,'seed':7,'seed_mode':'custom'})
  self.assertEqual(json.loads((job/'request.json').read_text(encoding='utf8'))['duration_seconds'],60)
 def test_make_plan_fills_series_defaults_and_prompts(self):
  with patch.object(pipeline,'JOBS',self.jobs):job=series.create_episode(self.root,'polar-night',1)
  state=pipeline.load(job/'state.json');plan=pipeline.make_plan(job,state)
  self.assertTrue(plan['series']);self.assertEqual(plan['planner_model'],'series-writer');self.assertEqual(plan['title'],'First Light')
  self.assertEqual(plan['final_frame'],'')
  shot=plan['shots'][0];self.assertEqual(shot['narration'],'Do you hear that?');self.assertEqual(shot['character'],'Alice')
  self.assertIn('subject_definitions:',shot['series_prompt']);self.assertIn('series_refs',shot)
  prov=json.loads((job/'request.json').read_text(encoding='utf8'))['provenance']
  self.assertEqual(prov['writer_model'],'Qwen3.5-9B-UD-Q4_K_XL.gguf');self.assertEqual(prov['voices'],{'alice':'en_US-amy-medium.onnx','bob':'en_US-amy-medium.onnx'})
  self.assertIn('MiniMaxH3ReferenceToVideo',prov['video_model']);self.assertIn('FLUX',prov['image_model'])
  self.assertEqual(json.loads((job/'plan.json').read_text(encoding='utf8')),plan)
 def test_make_plan_blocks_number_two_without_continuity(self):
  make_episode(self.root,number=2,episode_id='02-the-answer')
  with patch.object(pipeline,'JOBS',self.jobs):job=series.create_episode(self.root,'polar-night',2)
  with self.assertRaisesRegex(pipeline.JobError,'render the previous episode first'):pipeline.make_plan(job,pipeline.load(job/'state.json'))
 def test_make_plan_carries_previous_final_frame(self):
  previous=self.root/'polar-night/episodes/01-first-light';final=touch(previous/'final-frame.png')
  (previous/'continuity.json').write_text(json.dumps({'number':1,'ending_state':'Alice steps out.','next_hook':'The signal answers.','final_frame':str(final),'cast_refs':{}}),encoding='utf8')
  make_episode(self.root,number=2,episode_id='02-the-answer')
  with patch.object(pipeline,'JOBS',self.jobs):job=series.create_episode(self.root,'polar-night',2)
  plan=pipeline.make_plan(job,pipeline.load(job/'state.json'))
  self.assertEqual(plan['final_frame'],str(final))

def _patch_character():
 def fake_load(root,slug):return {'_dir':str(Path(root)/'characters'/slug),'portrait':'portrait.png'}
 return patch.object(series.registry,'load_character',side_effect=fake_load)

if __name__=='__main__':unittest.main()
