import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline

class LocalFilmTests(unittest.TestCase):
 def test_script_preserved_across_parts(self):
  text='First scene.\n\nSecond scene, exactly as written.'
  self.assertEqual(pipeline.script_parts(text),['First scene.','Second scene, exactly as written.'])
 def test_invalid_output_settings_rejected(self):
  with self.assertRaises(pipeline.JobError):pipeline.validate({'brief':'b','script':'s','style':'anime','width':1079,'height':1920})
 def test_input_reference_does_not_exist(self):
  with self.assertRaises(pipeline.JobError):pipeline.validate({'brief':'b','script':'s','style':'anime','references':['missing-image.png']})
 def test_remote_source_rejected(self):
  with self.assertRaises(pipeline.JobError):pipeline.local_path('https://example.com/reference.png')
 def test_foreign_comfy_is_not_used(self):
  with patch.object(pipeline,'api',return_value={'system':{'argv':['main.py','--base-directory','C:/someone-else']}}):
   with self.assertRaisesRegex(pipeline.JobError,'outside this project'):pipeline.ensure_server()
 def test_default_internal_resolution_and_boundaries(self):
  self.assertEqual(pipeline.internal_size(1080,1920),(704,1280));self.assertAlmostEqual(pipeline.SEGMENT,124/24)
 def test_interrupted_submission_is_not_blindly_repeated(self):
  with tempfile.TemporaryDirectory() as tmp:
   job=Path(tmp);(job/'segments').mkdir();state={'job_id':'test','segments':{'shot-01-00':{'prompt_id':'123','status':'submitting','graph':{},'started':1}}};shot={'id':'shot-01','voice':'unused.wav','character':'c','scene':'s','action':'a','prompt':'p'}
   with patch.object(pipeline,'BASE',job),patch.object(pipeline,'load',return_value={'157':{'inputs':{}},'142':{'inputs':{}},'18':{'inputs':{}},'19':{'inputs':{}},'130':{'inputs':{}},'136':{'inputs':{}}}),patch.object(pipeline,'locate',return_value=('unknown',None)),patch.object(pipeline.shutil,'copyfile'):
    (job/'input').mkdir()
    with self.assertRaisesRegex(pipeline.JobError,'Unknown outcome'):pipeline.render_segment(job,state,shot,0,None,{'width':1080,'height':1920,'style':'anime'})
if __name__=='__main__':unittest.main()
