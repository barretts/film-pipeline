import json,tempfile,threading,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from local_film import pipeline,server
from local_film.queue import FilmQueue

class FakeWorker:
 def __init__(self):self.done=False
 def poll(self):return 0 if self.done else None

class QueueTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.started=[]
  def spawn(job,mode):
   worker=FakeWorker();self.started.append((job.name,mode,worker));return worker
  self.q=FilmQueue(self.root,spawn)
 def tearDown(self):self.temp.cleanup()
 def make(self,name,created):
  p=self.root/name;p.mkdir();pipeline.atomic(p/'state.json',{'job_id':name,'status':'created','created':created});return p
 def test_fifo_and_cancel_queued(self):
  a=self.make('a',1);b=self.make('b',2);c=self.make('c',3)
  for job in (a,b,c):self.q.enqueue(job,'run')
  self.q.tick();self.assertEqual([x[0] for x in self.started],['a'])
  self.assertEqual(self.q.cancel(b)['status'],'cancelled')
  self.q.tick();self.assertEqual(len(self.started),1)
  pipeline.atomic(a/'state.json',{'job_id':'a','status':'complete','created':1});self.started[0][2].done=True
  self.q.tick();self.assertEqual([x[0] for x in self.started],['a','c'])
  self.assertEqual(pipeline.load(b/'state.json')['status'],'cancelled')
 def test_cancel_running_waits_for_worker_before_next_job(self):
  a=self.make('a',1);b=self.make('b',2);self.q.enqueue(a,'run');self.q.enqueue(b,'run');self.q.tick()
  self.assertEqual(self.q.cancel(a)['status'],'cancelling');self.q.tick();self.assertEqual(len(self.started),1)
  state=pipeline.load(a/'state.json');state['status']='planning';pipeline.atomic(a/'state.json',state)
  self.started[0][2].done=True;self.q.tick()
  self.assertEqual(pipeline.load(a/'state.json')['status'],'cancelled');self.assertEqual([x[0] for x in self.started],['a','b'])
 def test_only_owned_prompt_is_interrupted(self):
  a=self.make('a',1);pipeline.atomic(a/'state.json',{'job_id':'a','status':'rendering','created':1,'segments':{'x':{'status':'submitted'}}});self.q.cancel(a)
  q={'queue_running':[[0,'foreign',{}, {'client_id':'other'}],[1,'ours',{}, {'client_id':'local-film-a'}]],'queue_pending':[]}
  with patch('local_film.queue.api',return_value=q),patch.object(self.q,'_comfy_post') as post:self.q.tick();post.assert_called_once_with('/interrupt',{'prompt_id':'ours'})
 def test_legacy_active_worker_blocks_queue(self):
  a=self.make('a',1);b=self.make('b',2);pipeline.atomic(a/'state.json',{'job_id':'a','status':'rendering','created':1});self.q.enqueue(b,'run')
  with patch.object(self.q,'_owns_job',return_value=True):self.q.tick()
  self.assertEqual(self.started,[]);self.assertEqual(pipeline.load(b/'state.json')['status'],'queued')
 def test_cancel_survives_queue_recreation(self):
  a=self.make('a',1);self.q.enqueue(a,'run');self.q.cancel(a)
  restarted=FilmQueue(self.root,self.q.spawn);restarted.tick();self.assertEqual(self.started,[])
 def test_plan_jobs_use_same_queue(self):
  a=self.make('a',1);self.q.enqueue(a,'plan');self.q.tick();self.assertEqual(self.started[0][:2],('a','plan'))
 def test_crash_recovery_is_bounded(self):
  a=self.make('a',1);pipeline.atomic(a/'state.json',{'job_id':'a','status':'rendering','created':1,'queue_attempts':2})
  self.q.tick();self.assertEqual(pipeline.load(a/'state.json')['status'],'failed');self.assertEqual(self.started,[])
 def test_http_queue_and_cancel(self):
  with patch.object(server,'QUEUE',self.q),patch.object(server,'JOBS',self.root),patch.object(pipeline,'JOBS',self.root):
   http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
   try:
    base='http://127.0.0.1:'+str(http.server_port);op=urllib.request.build_opener(urllib.request.ProxyHandler({}));body={'mode':'run','request':{'brief':'A signal','script':'Hello there.','style':'anime'}}
    req=urllib.request.Request(base+'/api/jobs',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'});created=json.load(op.open(req));ident=created['job_id']
    listed=json.load(op.open(base+'/api/jobs'));self.assertEqual([(x['job_id'],x['status']) for x in listed],[(ident,'queued')])
    (self.root/ident/'worker.log').write_text('render progress 50%',encoding='utf8')
    logs=json.load(op.open(base+'/api/jobs/'+ident+'/logs'));self.assertIn('render progress 50%',logs['text'])
    req=urllib.request.Request(base+'/api/jobs/'+ident+'/cancel',data=b'',method='POST');self.assertEqual(json.load(op.open(req))['status'],'cancelled')
    self.q.tick();self.assertEqual(self.started,[])
   finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
