import json,time
from pathlib import Path
from unittest.mock import patch
from local_film import pipeline as P
job=P.JOBS/'20261030-123636-7525ee03'
video=job/'review'/'assembled.mp4'
before={str(p.relative_to(job)):P.hash_file(p) for p in [video,*sorted((job/'segments').glob('*.mp4'))]}
original=P.render_segment
original_api=P.api
def cached_only(job,state,shot,index,*args,**kwargs):
 path=job/'segments'/f"{shot['id']}-{index:02}.mp4"
 if not path.is_file():raise P.JobError('Recovery refuses generation: missing cached segment '+str(path))
 return original(job,state,shot,index,*args,**kwargs)
def guarded_api(path,payload=None):
 if payload is not None and path!='/free':raise P.JobError('Recovery refuses new ComfyUI submissions: '+path)
 return original_api(path,payload)
started=time.time()
with patch.object(P,'render_segment',side_effect=cached_only),patch.object(P,'api',side_effect=guarded_api):
 result=P.run(job,open_folder=False)
after={name:P.hash_file(job/name) for name in before}
if before!=after:raise RuntimeError('Existing video changed during finalization')
evidence={'status':result['status'],'elapsed_seconds':round(time.time()-started,2),'existing_media_unchanged':before==after,'sha256':after,'quality_flags':result.get('quality_flags',[]),'continuity':str(Path(P.load(job/'request.json')['episode_path'])/'continuity.json')}
Path('jobs/batch/recovery/result.json').write_text(json.dumps(evidence,indent=2))
print(json.dumps(evidence,indent=2))
