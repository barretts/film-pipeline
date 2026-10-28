import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline

class SeedTests(unittest.TestCase):
 def request(self,**extra):return dict(brief='A presenter at a desk',script='Hello there.',style='realistic',**extra)
 def test_random_is_selected_once_and_persisted(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(pipeline,'JOBS',Path(tmp)),patch.object(pipeline.secrets,'randbelow',side_effect=[1234,5678]) as random:
   first=pipeline.create(self.request(seed_mode='random',seed=None));second=pipeline.create(self.request())
   req=pipeline.load(first/'request.json');self.assertEqual(req['seed'],1234);self.assertEqual(pipeline.load(second/'request.json')['seed'],5678)
   self.assertEqual(pipeline.validate(req)['seed'],1234);self.assertEqual(random.call_count,2)
   self.assertEqual(pipeline.load(first/'state.json')['seed'],1234)
 def test_custom_seeds_preserve_zero_and_maximum(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(pipeline,'JOBS',Path(tmp)),patch.object(pipeline.secrets,'randbelow') as random:
   for seed in (0,4294967295):
    job=pipeline.create(self.request(seed_mode='custom',seed=seed));self.assertEqual(pipeline.load(job/'request.json')['seed'],seed)
   random.assert_not_called()
 def test_bad_custom_seeds_rejected(self):
  for value in (None,-1,4294967296,1.5,True,'123'):
   with self.subTest(value=value),self.assertRaises(pipeline.JobError):pipeline.validate(self.request(seed_mode='custom',seed=value))
  with self.assertRaises(pipeline.JobError):pipeline.validate(self.request(seed_mode='unknown'))
 def test_legacy_validation_does_not_assign_a_seed(self):
  self.assertNotIn('seed',pipeline.validate(self.request()))

if __name__=='__main__':unittest.main()
