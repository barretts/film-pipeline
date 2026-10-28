import math,shutil,tempfile,unittest,wave
from array import array
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline

class StopBeforeRender(Exception):pass

class OverlapTests(unittest.TestCase):
 def test_timeline_does_not_repeat_or_drop_time(self):
  req={'segment_frames':141,'continuation_overlap_frames':22}
  for seconds in (1,5.875,10.3,30):
   parts=pipeline.segment_schedule(seconds,req)
   self.assertAlmostEqual(sum(p['seconds'] for p in parts),seconds)
   cursor=0
   for part in parts:
    self.assertAlmostEqual(part['timeline_start'],cursor)
    self.assertAlmostEqual(part['audio_start']+part['trim_start'],cursor)
    cursor+=part['seconds']
   if len(parts)>1:self.assertAlmostEqual(parts[1]['audio_start'],119/24)
 def test_legacy_schedule_is_preserved(self):
  parts=pipeline.segment_schedule(10.3,{})
  self.assertEqual(len(parts),2);self.assertEqual(parts[1]['trim_start'],0);self.assertAlmostEqual(parts[1]['audio_start'],124/24)
 def test_motion_guide_and_audio_offset_in_submitted_graph(self):
  template=pipeline.load(pipeline.BASE/'ref2va-audio-comparison-graph.json')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);base=root/'comfy';(base/'input').mkdir(parents=True);job=root/'job';job.mkdir();pipeline.atomic(base/'ref2va-audio-comparison-graph.json',template)
   audio=root/'voice.wav';audio.write_bytes(b'fixture');image=root/'tail.png';image.write_bytes(b'fixture');video=root/'tail.mp4';video.write_bytes(b'fixture')
   shot={'id':'shot-01','voice':str(audio),'character':'adult','scene':'desk','action':'install','prompt':'desk','continuation_action':'speak with empty hands'};state={'job_id':'test','segments':{},'events':[]}
   req={'width':1080,'height':1920,'style':'realistic','segment_frames':141,'continuation_overlap_frames':22,'segment_instructions':'Keep camera static.'}
   with patch.object(pipeline,'BASE',base),patch.object(pipeline,'wait_idle',side_effect=StopBeforeRender):
    with self.assertRaises(StopBeforeRender):pipeline.render_segment(job,state,shot,1,image,req,video)
   g=state['segments']['shot-01-01']['graph'];self.assertEqual(g['163']['class_type'],'MiniMaxH3AddGuide');self.assertEqual(g['162']['inputs']['frame_load_cap'],22);self.assertEqual(g['142']['inputs']['image'],['162',0]);self.assertEqual(g['19']['inputs']['positive'],['163',0]);self.assertAlmostEqual(g['19']['inputs']['start_seconds'],119/24);self.assertNotIn('first_frame',g['157']['inputs']);self.assertTrue(g['157']['inputs']['prompt'].endswith('Keep camera static.'))
 @unittest.skipUnless(shutil.which('ffmpeg'),'ffmpeg required for media timing check')
 def test_real_audio_is_not_repeated_at_overlap(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);(job/'review').mkdir();voice=job/'voice.wav';rate=16000;seconds=10.3
   samples=array('h',(int(10000*math.sin(2*math.pi*(180*(n/rate)+35*(n/rate)**2))) for n in range(round(rate*seconds))))
   with wave.open(str(voice),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate);f.writeframes(samples.tobytes())
   req={'segment_frames':141,'continuation_overlap_frames':22,'width':256,'height':256,'fps':24};parts=pipeline.segment_schedule(seconds,req);segments=[]
   for part in parts:
    path=job/f"raw-{part['index']}.mp4"
    pipeline.run_cmd(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=gray:s=256x256:r=24:d=5.875','-ss',str(part['audio_start']),'-i',voice,'-t','5.875','-af','apad','-c:v','libx264','-preset','ultrafast','-c:a','aac',path])
    if part['index']:
     tail=pipeline.extract_motion_tail(segments[0][0],job/'tail.mp4',req);self.assertAlmostEqual(pipeline.duration(tail),22/24,places=2)
     path=pipeline.trim_overlap(path,job/'aligned'/path.name,part)
    segments.append((path,part['seconds']))
   output=pipeline.assemble(job,{},req,segments)
   self.assertLess(abs(pipeline.duration(output)-seconds),.08)
   self.assertGreater(pipeline.correlation(pipeline.audio_vector(voice),pipeline.audio_vector(output)),.9)

if __name__=='__main__':unittest.main()
