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
 return characters.load_show(root,'polar-night'),characters.load_cast(root,show)

class SeriesScheduleTests(unittest.TestCase):
 def setUp(self):
  self._tmp=tempfile.TemporaryDirectory();self.root=Path(self._tmp.name);self.show,self.cast=build_tree(self.root)
  self.job=Path(self._tmp.name)/'job';(self.job/'voices').mkdir(parents=True);self.silent=self.root/'silent.wav';self.silent.write_bytes(b'RIFFfake')
  def fake_line(exe,model,text,target):target.write_bytes(b'RIFFfake');return target
  self._line=patch.object(series,'_piper_line',side_effect=fake_line)
  self._run=patch.object(series,'run_cmd',side_effect=lambda args,**kw:Path(args[-1]).write_bytes(b'RIFFfake'))
  durations={'shot-01-00.line.wav':2.0,'shot-01-01.line.wav':4.0,'shot-01.merged.partial.wav':6.0,'shot-01.wav':6.0,'shot-02-00.line.wav':3.5,'shot-02.merged.partial.wav':3.5,'shot-02.wav':3.5,'shot-03-00.line.wav':2.0,'shot-03.merged.partial.wav':2.0,'shot-03.wav':2.0}
  self._duration=patch.object(series,'duration',side_effect=lambda path:durations.get(Path(path).name,0.5))
  self._line.start();self._run.start();self._duration.start()
  self.addCleanup(lambda:(self._line.stop(),self._run.stop(),self._duration.stop()))
 def shots(self):
  return [{'id':'shot-01','dialogue':[{'character':'alice','text':'One two.'},{'character':'bob','text':'Three four five.'}]},
   {'id':'shot-02','dialogue':[{'character':'bob','text':'Six seven.'}]},
   {'id':'shot-03','dialogue':[{'character':'alice','text':'Eight.'}]}]
 def request(self,**over):
  req={'kind':'series','show':'polar-night','episode':'01-first-light','series_root':str(self.root),'duration_seconds':0,'segment_frames':124,'continuation_overlap_frames':0}
  req.update(over);(self.job/'request.json').write_text(json.dumps(req),encoding='utf8');return req
 def test_duration_zero_auto_minimum_and_boundaries(self):
  self.request();plan={'shots':self.shots()};state={'events':[]}
  plan=series.voice_tracks(plan,self.cast,self.job,state=state)
  self.assertAlmostEqual(plan['shots'][0]['voice_seconds'],6.0);self.assertAlmostEqual(plan['shots'][1]['voice_seconds'],3.5)
  minimum=6.25+3.75+2.25
  self.assertAlmostEqual(sum(s['duration_seconds']for s in plan['shots']),minimum,places=6)
  self.assertAlmostEqual(plan['shots'][0]['duration_seconds'],6.25)
  schedule=pipeline.segment_schedule(6.25,self.request())
  self.assertEqual(plan['shots'][0]['continuation_boundaries_seconds'],[round(part['timeline_start'],3)for part in schedule[1:]])
  self.assertEqual(len(schedule),2)
  self.assertEqual(json.loads((self.job/'plan.json').read_text(encoding='utf8'))['shots'][0]['voice'],str(self.job/'voices'/'shot-01.wav'))
 def test_long_shot_needs_multiple_segments(self):
  self.request();plan={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'a'}]}]}
  with patch.object(series,'duration',side_effect=lambda path:15.0):series.voice_tracks(plan,self.cast,self.job,state={'events':[]})
  self.assertAlmostEqual(plan['shots'][0]['duration_seconds'],15.25)
  self.assertEqual(len(pipeline.segment_schedule(15.25,self.request())),3)
  overlap=self.request(continuation_overlap_frames=22)
  self.assertEqual(len(pipeline.segment_schedule(15.25,overlap)),4)
 def test_explicit_target_spreads_extra_and_pauses_padded(self):
  self.request(duration_seconds=45);plan={'shots':self.shots()};minimum=12.25
  series.voice_tracks(plan,self.cast,self.job,state={'events':[]})
  self.assertAlmostEqual(sum(s['duration_seconds']for s in plan['shots']),45,places=6)
  self.assertAlmostEqual(plan['shots'][0]['duration_seconds']/plan['shots'][2]['duration_seconds'],6.25/2.25,places=6)
 def test_too_short_target_rejected(self):
  self.request(duration_seconds=30);plan={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'x'}]}]}
  with patch.object(series,'duration',side_effect=lambda path:30.0):
   with self.assertRaisesRegex(pipeline.JobError,'shorter than narration'):series.voice_tracks(plan,self.cast,self.job,state={'events':[]})
 def test_line_concat_graph_and_gaps(self):
  self.request();calls=[]
  def record(args,**kw):Path(args[-1]).write_bytes(b'RIFF');calls.append(args)
  def fake_duration(path):
   name=Path(path).name
   return 1.35 if name.startswith('shot-01.') or name=='shot-01.wav' else 0.5
  with patch.object(series,'run_cmd',side_effect=record),patch.object(series,'duration',side_effect=fake_duration):
   series.voice_tracks({'shots':[self.shots()[0]]},self.cast,self.job,state={'events':[]})
  args=next(x for x in calls if '-filter_complex' in x)
  graph=args[args.index('-filter_complex')+1]
  self.assertEqual(graph.count('anullsrc=r=22050:cl=mono:d=0.35'),1)
  self.assertIn('concat=n=3:v=0:a=1',graph)
 def test_pauses_use_adelay_apad(self):
  self.request();plan={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'x'}]}]}
  calls=[]
  def fake(args,**kw):Path(args[-1]).write_bytes(b'RIFF');calls.append(args)
  def fake_duration(path):return 5.0 if Path(path).name.startswith('shot-01.') and 'merged' not in Path(path).name and Path(path).name!='shot-01-00.line.wav' else 3.0
  with patch.object(series,'run_cmd',side_effect=fake),patch.object(series,'duration',side_effect=fake_duration):
   series.voice_tracks(plan,self.cast,self.job,1.0,1.0,state={'events':[]})
  graph=next(x for x in calls if '-af' in x)
  self.assertIn('adelay=1000:all=1',graph[graph.index('-af')+1]);self.assertIn('apad=pad_dur=1',graph[graph.index('-af')+1])
  self.assertAlmostEqual(plan['shots'][0]['voice_seconds'],5.0)
 def test_truncated_pad_rejected(self):
  self.request();plan={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'x'}]}]}
  def fake(args,**kw):Path(args[-1]).write_bytes(b'RIFF')
  def fake_duration(path):return 5.0
  with patch.object(series,'run_cmd',side_effect=fake),patch.object(series,'duration',side_effect=fake_duration):
   with self.assertRaisesRegex(pipeline.JobError,'truncated'):series.voice_tracks(plan,self.cast,self.job,2.0,2.0,state={'events':[]})
 def test_resume_skips_synthesis_and_changed_text_rejected(self):
  self.request();plan={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'x'}]}]};state={'events':[]}
  series.voice_tracks(plan,self.cast,self.job,state=state)
  self.assertTrue((self.job/'voices'/'shot-01.wav').is_file())
  def explode(*a,**k):raise AssertionError('must not synthesize on resume')
  with patch.object(series,'_piper_line',side_effect=explode):series.voice_tracks(plan,self.cast,self.job,state=state)
  changed={'shots':[{'id':'shot-01','dialogue':[{'character':'alice','text':'x y'}]}]}
  with self.assertRaisesRegex(pipeline.JobError,'does not match current dialogue'):series.voice_tracks(changed,self.cast,self.job,state=state)
 def test_hash_guard_variant_isolated_across_pause_changes(self):
  self.request();shots=self.shots()[:1]
  state={'events':[]}
  series.voice_tracks({'shots':shots},self.cast,self.job,state=state)
  def explode(*a,**k):raise AssertionError('must not resynthesize identical unpadded dialogue')
  with patch.object(series,'_piper_line',side_effect=explode):series.voice_tracks({'shots':self.shots()[:1]},self.cast,self.job,state=state)
 def test_segment_schedule_overlap_window(self):
  plain=pipeline.segment_schedule(15.25,self.request());overlap=self.request(continuation_overlap_frames=22)
  parts=pipeline.segment_schedule(15.25,overlap)
  self.assertEqual(len(plain),3);self.assertEqual(len(parts),4)
  self.assertLess(parts[1]['audio_start'],plain[1]['audio_start'])
  self.assertAlmostEqual(parts[1]['seconds'],(124-22)/24)
  self.assertEqual(parts[0]['seconds'],124/24)
if __name__=='__main__':unittest.main()
