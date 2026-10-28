import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline

class BeforeSubmission(Exception):pass

class SegmentInstructionsTests(unittest.TestCase):
 def test_instructions_survive_every_prompt_path(self):
  template=pipeline.load(pipeline.BASE/'ref2va-audio-comparison-graph.json')
  rules='Camera stays static.\nNo zoom. Keep the desk in frame.'
  for index,reference,object_reference in [(0,False,False),(0,True,False),(1,True,False),(0,False,True),(0,True,True),(1,True,True)]:
   with self.subTest(index=index,reference=reference,object_reference=object_reference),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);base=root/'comfy';(base/'input').mkdir(parents=True);job=root/'job';job.mkdir()
    pipeline.atomic(base/'ref2va-audio-comparison-graph.json',template)
    audio=root/'speech.wav';audio.write_bytes(b'fixture');ref=root/'ref.png';ref.write_bytes(b'fixture')
    state={'job_id':'test','segments':{},'events':[]}
    req={'width':1080,'height':1920,'style':'realistic','segment_instructions':rules}
    if object_reference:req['staged_object_reference']={'path':str(ref)}
    shot={'id':'shot-01','voice':str(audio),'character':'An adult presenter','scene':'At a desk','action':'Installs a card','prompt':'At a desk','continuation_action':'Smiles at the viewer'}
    with patch.object(pipeline,'BASE',base),patch.object(pipeline,'wait_idle',side_effect=BeforeSubmission):
     with self.assertRaises(BeforeSubmission):pipeline.render_segment(job,state,shot,index,ref if reference else None,req)
    graph=state['segments'][f'shot-01-{index:02}']['graph'];self.assertTrue(graph['157']['inputs']['prompt'].endswith(rules))
    if index:
     self.assertNotIn('Installs a card',graph['157']['inputs']['prompt'])
     self.assertEqual(graph['157']['class_type'],'MiniMaxH3DistilledImageToVideo')
     self.assertEqual(graph['157']['inputs']['first_frame'],['142',0])
     self.assertEqual(graph['19']['inputs']['positive'],['157',0])
     self.assertEqual(graph['19']['inputs']['latent'],['157',1])
     self.assertNotIn('161',graph)
 def test_invalid_instructions_rejected_and_legacy_requests_supported(self):
  req={'brief':'A demonstration','script':'Hello there.','style':'realistic'}
  self.assertEqual(pipeline.validate(dict(req))['segment_instructions'],'')
  for invalid in [None,[],200,'x'*2001]:
   with self.subTest(value=type(invalid)),self.assertRaises(pipeline.JobError):pipeline.validate(dict(req,segment_instructions=invalid))

if __name__=='__main__':unittest.main()
