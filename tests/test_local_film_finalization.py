import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_film import pipeline as P


class FinalizationTests(unittest.TestCase):
 def test_tail_uses_last_video_frame_when_audio_extends_container(self):
  if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
   self.skipTest('FFmpeg required')
  from PIL import Image
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);video=root/'short.mp4';target=root/'tail.png'
   P.run_cmd(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=red:s=32x32:r=10:d=0.1','-f','lavfi','-i','color=blue:s=32x32:r=10:d=0.1','-f','lavfi','-i','anullsrc=r=8000:cl=mono:d=1','-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0[v]','-map','[v]','-map','2:a','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',video])
   P.extract_tail(video,target)
   with Image.open(target) as image:
    red,green,blue=image.convert('RGB').getpixel((16,16))
   self.assertGreater(blue,200);self.assertLess(red,30)
   self.assertFalse((root/'tail.partial.png').exists())
   # An already finalized frame must not require the source or be overwritten.
   before=target.read_bytes();video.unlink();P.extract_tail(video,target)
   self.assertEqual(target.read_bytes(),before)

 def test_tail_empty_decode_reports_error_without_publishing(self):
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp)/'tail.png'
   with patch.object(P,'run_cmd') as run:
    run.return_value.stdout=json.dumps({'streams':[{'nb_read_frames':'0'}]}).encode()
    with self.assertRaisesRegex(P.JobError,'No video frames'):P.extract_tail(Path('bad.mp4'),target)
   self.assertFalse(target.exists())

 def test_series_quality_skips_cards_and_offsets_assembled_audio(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);(job/'review').mkdir()
   title=job/'title-card.mp4';segment=job/'shot-01-00.mp4';end=job/'end-card.mp4';voice=job/'voice.wav';output=job/'review'/'assembled.mp4'
   samples=[0.25,-0.25]*4000
   def audio(path):
    if path==output:return [0.0]*16000+samples+[0.0]*16000
    if path in (voice,segment):return samples
    raise AssertionError('Cards must not be checked as dialogue segments')
   plan={'shots':[{'id':'shot-01','voice':str(voice),'duration_seconds':1}]}
   req={'kind':'series','width':32,'height':32}
   info={'streams':[{'codec_type':'video','width':32,'height':32},{'codec_type':'audio'}],'format':{'duration':'5'}}
   with patch.object(P,'media',return_value=info),patch.object(P,'duration',return_value=5),patch.object(P,'run_cmd'),patch.object(P,'audio_vector',side_effect=audio),patch.object(P,'segment_schedule',return_value=[{'timeline_start':0,'seconds':1}]),patch.object(P,'visual_stats',return_value={'mean_difference':2,'max_change_from_first':3}):
    report=P.quality(job,plan,req,[(title,2),(segment,1),(end,2)],output)
   self.assertEqual(report['assembled_audio_checks'][0]['correlation'],1)
   self.assertEqual([entry['segment'] for entry in report['checks']],[segment.name])
   self.assertEqual(report['flags'],[])


if __name__=='__main__':unittest.main()
