"""GPU execution contracts tested exclusively with fakes and CPU media."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from PIL import Image

from local_film.project_contract import ProjectError, digest
from local_film.project_gpu import ComfyTransport, GpuWorker, SubmissionRejected, graph_values_hash
from local_film.project_inputs import bind_image, execution_inputs
from local_film.projects import FilmProjects, media
from local_film.project_graphs import request_bundle

ROOT = Path(__file__).resolve().parent.parent


class FakeTransport:
    def __init__(self, on_submit=None, observations=None):
        self.on_submit = on_submit
        self.observations = list(observations or [{'state': 'running'}])
        self.submissions, self.cancellations = [], []
        self.record = None

    def queue(self): return {'queue_running': [], 'queue_pending': []}
    def stage(self, bundle, inputs): return copy.deepcopy(bundle['graph'])
    def submit(self, graph, record):
        self.record = copy.deepcopy(record); self.submissions.append(self.record)
        if self.on_submit: self.on_submit(record)
        return {'prompt_id': record['prompt_id']}
    def observe(self, record):
        if self.cancellations: return {'state': 'absent'}
        return self.observations.pop(0) if len(self.observations) > 1 else self.observations[0]
    def cancel(self, record): self.cancellations.append(record['prompt_id']); return {'cancelled': True}
    def output(self, observed, bundle): raise AssertionError('Output path was not provided by this fixture')


class GpuProjectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = FilmProjects(self.root / 'projects')
        spec = json.loads((ROOT / 'examples/signalInTheSnow.json').read_text(encoding='utf8'))
        spec['shots'] = spec['shots'][:1]
        self.pid = self.service.create(spec, 'gpu-contract-fixture')['project_id']
        folder = self.service.store.directory(self.pid); folder.mkdir()
        self.audio = folder / 'sound.wav'; self.audio.write_bytes(b'technical audio fixture')
        self.card = folder / 'timing.mp4'; self.card.write_bytes(b'technical timing fixture')
        self.image = self.root / 'room.png'; Image.new('RGB', (1280, 704), 'navy').save(self.image)
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid)
            aid = self.service._register_files(project, [self.card])[str(self.card.resolve())]
            project['preparation'] = {'id': 'fixture-preparation', 'spec_hash': digest(project['spec']),
                'animatic_artifact_id': aid, 'characters': {}, 'shots': {'radioWarning': {
                    'audio': str(self.audio), 'audio_hash': media.file_hash(self.audio)}}}
            self.service.store.save(db, project)
        self.counter = 0
        self.command('approve-storyboard', human=True)
        self.command('render-ready')
        self.tid = self.get()['takes'][0]['id']
        self.name = f'films/{self.pid}/{self.tid}/reference-0.png'

    def tearDown(self): self.temporary.cleanup()
    def get(self): return self.service.get(self.pid)
    def take(self): return next(t for t in self.get()['takes'] if t['id'] == self.tid)
    def command(self, action, payload=None, human=False):
        self.counter += 1
        return self.service.command(self.pid, {'command_id': f'fixture-{self.counter}', 'action': action,
            'expected_revision': self.get()['revision'], 'payload': payload or {}}, human=human)
    def ready(self):
        bind_image(self.service, self.pid, self.tid, self.name, self.image, self.get()['revision'])
        self.command('approve-inputs', {'take_id': self.tid}, human=True)
    def worker(self, transport):
        self.now = 0
        def sleep(seconds): self.now += seconds
        return GpuWorker(self.service, transport, enabled=True, lock_root=self.root / 'locks',
                         clock=lambda: self.now, sleep=sleep)

    def test_default_worker_does_not_read_project_lock_files_or_transport(self):
        with patch('local_film.project_gpu.pipeline.locked', side_effect=AssertionError('lock touched')):
            worker = GpuWorker(None, object())
            self.assertEqual(worker.run_one('unused', 'unused'), {'state': 'disabled', 'submitted': False})

    def test_silent_radio_can_use_approved_room_as_a_locked_first_frame(self):
        project = self.get(); shot = copy.deepcopy(project['spec']['shots'][0])
        shot['conditioning_mode'] = 'first-frame'
        bundle = request_bundle(project, shot, self.take())
        self.assertEqual(bundle['conditioning_mode'], 'first-frame')
        self.assertEqual(bundle['graph']['6']['class_type'], 'MiniMaxH3ImageToVideo')
        self.assertIn('locked camera', bundle['graph']['6']['inputs']['prompt'])
        self.assertNotIn('precise lip movements', bundle['graph']['6']['inputs']['prompt'])
        image = next(i for i in bundle['required_inputs'] if i['name'].endswith('first-frame.png'))
        self.assertEqual(image['kind'], 'room-reference')
        self.assertEqual(image['references'], {})

    def test_required_image_is_immutable_and_needs_separate_human_review(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(ProjectError, 'human approval'):
            self.worker(transport).run_one(self.pid, self.tid)
        bind_image(self.service, self.pid, self.tid, self.name, self.image, self.get()['revision'])
        with self.assertRaises(ProjectError): self.command('approve-inputs', {'take_id': self.tid})
        self.command('approve-inputs', {'take_id': self.tid}, human=True)
        first = self.take()['input_bindings'][self.name]['artifact_id']
        revision = self.get()['revision']
        bind_image(self.service, self.pid, self.tid, self.name, self.image, revision)
        self.assertEqual(self.get()['revision'], revision)
        Image.new('RGB', (1280, 704), 'green').save(self.image)
        bind_image(self.service, self.pid, self.tid, self.name, self.image, revision)
        self.assertNotIn('input_approval', self.take())
        self.assertNotEqual(self.take()['input_bindings'][self.name]['artifact_id'], first)
        old, _ = self.service.artifact(self.pid, first)
        self.assertNotEqual(media.file_hash(old), media.file_hash(self.image))
        self.assertFalse(transport.submissions)

    def test_bad_size_and_nonrequired_binding_are_rejected(self):
        with self.assertRaises(ProjectError):
            bind_image(self.service, self.pid, self.tid, '../escape.png', self.image, self.get()['revision'])
        Image.new('RGB', (100, 100)).save(self.image)
        with self.assertRaisesRegex(ProjectError, '1280 by 704'):
            bind_image(self.service, self.pid, self.tid, self.name, self.image, self.get()['revision'])

    def test_staged_or_bound_input_tampering_blocks_submission(self):
        self.ready()
        path, _ = self.service.artifact(self.pid, self.take()['input_bindings'][self.name]['artifact_id'])
        path.write_bytes(b'changed')
        transport = FakeTransport()
        with self.assertRaisesRegex(ProjectError, 'changed after publication'):
            self.worker(transport).run_one(self.pid, self.tid)
        self.assertFalse(transport.submissions)

    def test_lost_submission_response_persists_identity_and_never_resubmits(self):
        self.ready()
        def lost(record):
            saved = self.take()['gpu']
            self.assertEqual(saved['prompt_id'], record['prompt_id'])
            self.assertEqual(saved['state'], 'submitting')
            self.service.artifact(self.pid, saved['manifest_artifact_id'])
            raise TimeoutError('response was lost')
        transport = FakeTransport(on_submit=lost, observations=[{'state': 'absent'}])
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'submission-unknown')
        saved_id = self.take()['gpu']['prompt_id']
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'submission-unknown')
        self.assertEqual(len(transport.submissions), 1)
        self.assertEqual(self.take()['gpu']['prompt_id'], saved_id)
        for action in ('update', 'resume', 'render-ready', 'prepare-assets'):
            with self.subTest(action=action), self.assertRaisesRegex(ProjectError, 'reconciliation'):
                self.command(action, {'spec': self.get()['spec']} if action == 'update' else {})
        self.command('cancel')
        self.assertEqual(self.get()['status'], 'cancel-pending')
        self.command('cancel')  # A repeated explicit cancellation is harmless.
        self.assertEqual(self.get()['status'], 'cancel-pending')
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'cancel-pending')
        self.assertFalse(transport.cancellations)  # Never observed ownership on server.

    def test_owned_running_cancellation_waits_for_confirmed_absence(self):
        self.ready()
        transport = FakeTransport(on_submit=lambda _: self.command('cancel'))
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'cancelled')
        self.assertEqual(transport.cancellations, [self.take()['gpu']['prompt_id']])
        self.assertEqual(self.get()['status'], 'cancelled')
        self.assertFalse(self.get()['gpu_active'])

    def test_cancel_can_reconcile_even_if_prepared_audio_was_lost(self):
        self.ready()
        transport = FakeTransport(on_submit=lambda _: (_ for _ in ()).throw(TimeoutError()))
        self.worker(transport).run_one(self.pid, self.tid)
        self.audio.unlink()
        self.command('cancel')
        transport.observations = [{'state': 'running'}]
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'cancelled')
        self.assertEqual(len(transport.submissions), 1)

    def test_unconfirmed_cancel_and_foreign_ownership_keep_reservation(self):
        self.ready()
        transport = FakeTransport(on_submit=lambda _: self.command('cancel'))
        def not_owned(record): raise ProjectError('different client or take')
        transport.observe = not_owned
        result = self.worker(transport).run_one(self.pid, self.tid)
        self.assertEqual(result['state'], 'cancel-pending')
        self.assertTrue(self.get()['gpu_active'])
        self.assertFalse(transport.cancellations)

    def test_timeout_requests_owned_cancellation_without_resubmission(self):
        self.ready(); transport = FakeTransport()
        result = self.worker(transport).run_one(self.pid, self.tid, timeout=2, poll_seconds=1)
        self.assertEqual(result['state'], 'cancelled')
        self.assertEqual(len(transport.submissions), 1)
        self.assertEqual(len(transport.cancellations), 1)

    def test_cancellation_timeout_retains_active_reservation(self):
        self.ready(); transport = FakeTransport(on_submit=lambda _: self.command('cancel'))
        transport.observe = lambda _: {'state': 'running'}
        result = self.worker(transport).run_one(self.pid, self.tid, cancel_timeout=2, poll_seconds=1)
        self.assertEqual(result['state'], 'cancel-pending')
        self.assertEqual(self.get()['status'], 'cancel-pending')
        self.assertTrue(self.get()['gpu_active'])

    def test_cancel_releases_a_crashed_preflight_without_submitting(self):
        self.ready()
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid)
            project['takes'][0]['gpu'] = {'state': 'preparing'}
            self.service.store.save(db, project)
        self.command('cancel'); transport = FakeTransport()
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'cancelled')
        self.assertFalse(self.get()['gpu_active']); self.assertFalse(transport.submissions)

    def test_explicit_rejection_is_terminal_and_never_automatically_retried(self):
        self.ready()
        transport = FakeTransport(on_submit=lambda _: (_ for _ in ()).throw(SubmissionRejected('bad node')))
        worker = self.worker(transport)
        self.assertEqual(worker.run_one(self.pid, self.tid)['state'], 'rejected')
        self.assertEqual(worker.run_one(self.pid, self.tid)['state'], 'rejected')
        self.assertEqual(len(transport.submissions), 1)
        self.assertTrue(self.take()['gpu']['submitted_at'])

    def test_nonfinite_timeouts_cannot_disable_the_stop_bound(self):
        for timeout in (float('inf'), float('nan'), -1):
            with self.subTest(timeout=timeout), self.assertRaises(ProjectError):
                self.worker(FakeTransport()).run_one(self.pid, self.tid, timeout=timeout)

    def test_failed_execution_consumes_retry_budget_without_an_output(self):
        self.ready()
        transport = FakeTransport(observations=[{'state': 'failed', 'history': {'status': 'error'}}])
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'failed')
        self.command('render-ready')
        self.assertEqual(self.get()['status'], 'awaiting-owner-decision')
        self.assertIn('already attempted', self.get()['blocked_shots'][0]['reason'])
        self.assertEqual(len(self.get()['takes']), 1)
        spec = self.get()['spec']; spec['shots'][0]['camera'] += ', reframed'
        self.command('update', {'spec': spec})
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid)
            project['preparation']['spec_hash'] = digest(project['spec'])
            self.service.store.save(db, project)
        self.command('approve-storyboard', human=True)
        self.command('render-ready')
        self.assertEqual(len(self.get()['takes']), 1)
        self.assertIn('authorization', self.get()['blocked_shots'][0]['reason'])
        self.command('authorize-retry', {'shot_id': 'radioWarning', 'note': 'Changed framing'}, human=True)
        self.command('render-ready')
        self.tid = self.get()['takes'][-1]['id']; self.name = f'films/{self.pid}/{self.tid}/reference-0.png'
        self.ready()
        self.worker(transport).run_one(self.pid, self.tid)
        spec = self.get()['spec']; spec['shots'][0]['camera'] += ', closer'
        self.command('update', {'spec': spec})
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid); project['preparation']['spec_hash'] = digest(project['spec'])
            self.service.store.save(db, project)
        self.command('approve-storyboard', human=True); self.command('render-ready')
        self.assertIn('Two-take limit', self.get()['blocked_shots'][0]['reason'])
        self.assertEqual(len(transport.submissions), 2)

    def test_busy_foreign_queue_changes_no_service_and_consumes_no_attempt(self):
        self.ready(); transport = FakeTransport()
        transport.queue = lambda: {'queue_running': [['foreign prompt']], 'queue_pending': []}
        result = self.worker(transport).run_one(self.pid, self.tid)
        self.assertEqual(result['state'], 'preflight-failed')
        self.assertFalse(self.take()['gpu'].get('submitted_at'))
        self.assertEqual(self.take()['gpu']['service_changes'], 'none')
        self.assertFalse(transport.submissions)

    def test_pending_output_is_imported_once_without_a_server_or_new_prompt(self):
        self.ready()
        transport = FakeTransport(observations=[{'state': 'complete', 'history': {'outputs': {}}}])
        transport.output = lambda *_: self.root / 'missing-video.mp4'
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'output-pending')
        video = self.root / 'fixture.mp4'
        media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                       'color=blue:s=32x32:r=24:d=5', '-c:v', 'libx264', '-threads', '2', video])
        transport.output = lambda *_: video
        transport.observe = lambda *_: (_ for _ in ()).throw(AssertionError('Server should not be needed'))
        result = self.worker(transport).run_one(self.pid, self.tid)
        self.assertEqual(result['state'], 'awaiting-review')
        take = self.take()
        self.assertTrue(take['artifact_id']); self.assertTrue(take['end_frame']['sha256'])
        self.assertEqual(take['gpu']['state'], 'complete')
        self.assertFalse(self.get()['approved_takes'])
        self.command('render-ready')
        self.assertEqual(self.get()['status'], 'awaiting-review')
        self.assertEqual(len(self.get()['takes']), 1)
        self.assertEqual(self.worker(transport).run_one(self.pid, self.tid)['state'], 'complete')
        self.assertEqual(len(transport.submissions), 1)
        self.assertEqual(len(list((self.service.store.directory(self.pid) / 'takes' / self.tid).glob('video.*'))), 1)

    def test_short_video_cannot_be_published_as_a_full_take(self):
        video = self.root / 'short.mp4'
        media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                       'color=blue:s=32x32:r=24:d=1', '-c:v', 'libx264', '-threads', '2', video])
        with self.assertRaisesRegex(ProjectError, 'shorter than its approved shot'):
            self.service.import_take(self.pid, self.tid, video, self.get()['revision'])
        self.assertFalse(self.take()['artifact_id'])
        self.assertFalse((self.service.store.directory(self.pid) / 'takes' / self.tid / 'video.mp4').exists())

    def test_running_cpu_cancel_stays_pending_until_worker_has_stopped(self):
        started, release = threading.Event(), threading.Event()
        self.command('prepare-assets')
        def prepare(*args, **kwargs):
            started.set()
            if not release.wait(5): raise AssertionError('fixture release timed out')
            raise ProjectError('CPU work stopped after cancellation')
        with patch('local_film.projects.media.prepare', side_effect=prepare):
            thread = threading.Thread(target=self.service.tick)
            thread.start()
            try:
                self.assertTrue(started.wait(3))
                self.command('cancel')
                self.assertEqual(self.get()['status'], 'cancel-pending')
            finally:
                release.set(); thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.get()['status'], 'cancelled')

    def test_other_project_reservation_and_shared_lock_block_dispatch(self):
        self.ready()
        other = self.service.create(self.get()['spec'], 'other-project')
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, other['project_id'])
            project['takes'] = [{'id': 'another-take', 'gpu': {'state': 'submission-unknown'}}]
            self.service.store.save(db, project)
        with self.assertRaisesRegex(ProjectError, 'Another GPU request'):
            self.worker(FakeTransport()).run_one(self.pid, self.tid)
        with patch('local_film.project_gpu.pipeline.locked', side_effect=ProjectError('lock is owned')):
            with self.assertRaisesRegex(ProjectError, 'lock is owned'):
                self.worker(FakeTransport()).run_one(self.pid, self.tid)


class ComfyTransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.transport = ComfyTransport(self.root / 'input', self.root / 'output')
        self.graph = {'17': {'class_type': 'SaveVideo', 'inputs': {'filename_prefix': 'films/film-test/take-test'}}}
        self.record = {'prompt_id': '363727da-a6d8-4874-b11d-75c6bb315fca', 'client_id': 'client-test',
            'ownership': {'film_project_id': 'film-test', 'film_take_id': 'take-test'}, 'graph_hash': digest(self.graph)}
        self.entry = [0, self.record['prompt_id'], self.graph, dict(self.record['ownership'], client_id='client-test'), ['17']]
    def tearDown(self): self.temporary.cleanup()

    def test_loopback_configuration_and_ownership_checks(self):
        for url in ('https://127.0.0.1:8191', 'http://example.com', 'http://user:pass@localhost:8191'):
            with self.subTest(url=url), self.assertRaises(ProjectError): ComfyTransport(self.root, self.root, url)
        for mutation in ('client', 'take', 'graph'):
            entry = copy.deepcopy(self.entry)
            if mutation == 'client': entry[3]['client_id'] = 'foreign'
            if mutation == 'take': entry[3]['film_take_id'] = 'foreign'
            if mutation == 'graph': entry[2]['extra'] = {}
            with self.subTest(mutation=mutation), patch.object(self.transport, 'queue', return_value={'queue_running': [entry]}):
                with self.assertRaises(ProjectError): self.transport.observe(self.record)

    def test_output_path_and_filename_are_scoped_to_the_owned_take(self):
        bundle = {'project_id': 'film-test', 'take_id': 'take-test', 'graph': self.graph}
        for item in ({'filename': '../foreign.mp4'}, {'filename': 'foreign_00001.mp4', 'subfolder': 'films/film-test'},
                     {'filename': 'take-test_00001.mp4', 'subfolder': '../outside'},
                     {'filename': 'take-test_00001.mp4', 'subfolder': 'films/film-test', 'type': 'input'}):
            observed = {'history': {'outputs': {'17': {'images': [item]}}}}
            with self.subTest(item=item), self.assertRaises(ProjectError): self.transport.output(observed, bundle)

    def test_server_float_widget_coercion_preserves_identity_but_changed_values_do_not(self):
        self.graph['17']['inputs']['frame_rate'] = 24
        self.record.update(graph_hash=digest(self.graph), graph_values_hash=graph_values_hash(self.graph))
        self.entry[2] = copy.deepcopy(self.graph)
        self.entry[2]['17']['inputs']['frame_rate'] = 24.0
        ComfyTransport._owned(self.entry, self.record)
        self.entry[2]['17']['inputs']['frame_rate'] = 25.0
        with self.assertRaisesRegex(ProjectError, 'graph differs'): ComfyTransport._owned(self.entry, self.record)
        self.assertNotEqual(graph_values_hash({'value': True}), graph_values_hash({'value': 1}))
        self.assertNotEqual(graph_values_hash({'value': 2**53+1}), graph_values_hash({'value': float(2**53+1)}))

    def test_vhs_video_output_is_recovered_with_its_still_preview_ignored(self):
        self.graph['17']['class_type'] = 'VHS_VideoCombine'
        folder = self.root / 'output/films/film-test'; folder.mkdir(parents=True)
        video = folder / 'take-test_00001.mp4'; video.write_bytes(b'video fixture')
        bundle = {'project_id': 'film-test', 'take_id': 'take-test', 'graph': self.graph}
        observed = {'history': {'outputs': {'17': {'gifs': [
            {'filename': video.name, 'subfolder': 'films/film-test', 'type': 'output'}],
            'images': [{'filename': 'preview.png', 'subfolder': 'films/film-test'}]}}}}
        self.assertEqual(self.transport.output(observed, bundle), video)
        self.graph['17']['inputs']['filename_prefix'] = 'foreign/output'
        with self.assertRaisesRegex(ProjectError, 'Output prefix escaped'): self.transport.stage(bundle, [])

    def test_history_requires_the_same_owner_and_recognized_terminal_status(self):
        history = {'prompt': self.entry, 'status': {'completed': True, 'status_str': 'success'}, 'outputs': {}}
        def request(path, payload=None):
            return {'queue_running': [], 'queue_pending': []} if path == '/queue' else {self.record['prompt_id']: history}
        with patch.object(self.transport, 'request', side_effect=request):
            self.assertEqual(self.transport.observe(self.record)['state'], 'complete')
            history['prompt'][3]['client_id'] = 'foreign'
            with self.assertRaisesRegex(ProjectError, 'different client'): self.transport.observe(self.record)

    def test_wrong_submission_uuid_and_server_failure_remain_ambiguous(self):
        with patch.object(self.transport, 'request', return_value={'prompt_id': 'different'}):
            with self.assertRaisesRegex(ProjectError, 'reserved prompt UUID'): self.transport.submit(self.graph, self.record)
        for status in (400, 500):
            error = urllib.error.HTTPError('http://localhost/prompt', status, 'failed', {}, io.BytesIO(b'bad graph'))
            with self.subTest(status=status), patch.object(self.transport, 'request', side_effect=error):
                with self.assertRaises(SubmissionRejected if status == 400 else urllib.error.HTTPError):
                    self.transport.submit(self.graph, self.record)

    def test_staging_is_hash_verified_namespaced_and_never_overwrites(self):
        source = self.root / 'audio.wav'; source.write_bytes(b'sound')
        bundle = {'project_id': 'film-test', 'take_id': 'take-test', 'graph': {
            '18': {'class_type': 'LoadAudio', 'inputs': {'audio': 'films/film-test/take-test/audio.wav'}}}}
        item = {'name': 'films/film-test/take-test/audio.wav', 'source': str(source), 'sha256': media.file_hash(source)}
        self.transport.stage(bundle, [item]); self.transport.stage(bundle, [item])
        (self.root / 'input' / item['name']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ProjectError, 'refusing to overwrite'): self.transport.stage(bundle, [item])
        item['name'] = '../../outside.wav'
        with self.assertRaises(ProjectError): self.transport.stage(bundle, [item])

    def test_actual_http_transport_round_trip_uses_only_targeted_cancel(self):
        calls, entry, record = [], self.entry, self.record
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                calls.append(('GET', self.path))
                payload = {'queue_running': [entry], 'queue_pending': []} if self.path == '/queue' else {}
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(payload).encode())
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                calls.append(('POST', self.path, payload))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'prompt_id': record['prompt_id']} if self.path == '/prompt' else {'cancelled': True}).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            transport = ComfyTransport(self.root, self.root, f'http://127.0.0.1:{server.server_port}')
            transport.submit(self.graph, record)
            self.assertEqual(transport.observe(record)['state'], 'running')
            transport.cancel(record)
        finally:
            server.shutdown(); server.server_close(); thread.join(3)
        post = calls[0][2]
        self.assertEqual(post['prompt_id'], record['prompt_id'])
        self.assertEqual(post['extra_data'], record['ownership'])
        self.assertEqual(calls[-1], ('POST', '/api/jobs/' + record['prompt_id'] + '/cancel', {}))
        self.assertFalse(any(path in ('/interrupt', '/free') for _, path, *_ in calls))


if __name__ == '__main__': unittest.main()
