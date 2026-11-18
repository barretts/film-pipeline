import copy
import json
from pathlib import Path
import tempfile
import threading
import socket
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from local_film.project_contract import ProjectError, approved_takes, digest, validate_spec
from local_film.projects import FilmProjects, media
from local_film.project_server import FilmHTTPServer

ROOT = Path(__file__).resolve().parent.parent


def specification():
    return json.loads((ROOT / 'examples/signalInTheSnow.json').read_text(encoding='utf8'))


class FilmProjectTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = FilmProjects(self.root / 'projects')
        self.project = self.service.create(specification(), 'create-signal')
        self.pid = self.project['project_id']
        self.counter = 0

    def tearDown(self):
        self.temporary.cleanup()

    def get(self):
        return self.service.get(self.pid)

    def command(self, action, payload=None, human=False):
        self.counter += 1
        return self.service.command(self.pid, {'command_id': f'c{self.counter}',
            'expected_revision': self.get()['revision'], 'action': action, 'payload': payload or {}}, human=human)

    def prepared(self):
        def prepare(project, directory, registry, cancelled, **kwargs):
            directory.mkdir(parents=True)
            movie = directory / 'animatic.mp4'; movie.write_bytes(b'planning movie')
            return {'preparation': {'spec_hash': digest(project['spec']), 'animatic': str(movie),
                'characters': {}, 'shots': {s['id']: {'audio_hash': media.file_hash(movie), 'audio': str(movie), 'card': str(movie)}
                                             for s in project['spec']['shots']}},
                'files': [movie], 'primary': movie}
        self.command('prepare-assets')
        with patch('local_film.projects.media.prepare', side_effect=prepare):
            self.assertTrue(self.service.tick())
        self.assertEqual(self.get()['status'], 'awaiting-storyboard-review')

    def approve_board(self):
        self.prepared(); self.command('approve-storyboard', human=True)

    def prepare_takes(self):
        # Real recipe building, with a minimal registry manifest for this state-machine test.
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid)
            for member in project['spec']['characters']:
                project['preparation']['characters'][member] = {'files': [{'path': 'reference.png'}]}
            self.service.store.save(db, project)
        self.command('render-ready')

    def attach_and_approve(self, shot):
        take = next(t for t in reversed(self.get()['takes']) if t['shot_id'] == shot)
        with self.service.store.transaction() as db:
            project = self.service.store.read(db, self.pid)
            next(t for t in project['takes'] if t['id'] == take['id'])['artifact_id'] = project['preparation']['animatic_artifact_id']
            self.service.store.save(db, project)
        self.command('review', {'take_id': take['id'], 'decision': 'approve'}, human=True)
        return take

    def test_warning_loop_is_short_and_sources_are_explicit(self):
        spec = validate_spec(specification())
        self.assertEqual(sum(s['seconds'] for s in spec['shots']), 38)
        self.assertEqual(spec['shots'][0]['dialogue'][0]['text'], spec['shots'][-1]['dialogue'][0]['text'])
        self.assertEqual(spec['shots'][0]['dialogue'][0]['source'], 'radio')
        self.assertTrue(spec['shots'][4]['silence'])

    def test_bad_silence_and_future_dependency_and_state_are_rejected(self):
        for edit in ('silence', 'dependency', 'state', 'speaker'):
            spec = specification()
            if edit == 'silence': spec['shots'][0]['silence'] = True
            if edit == 'dependency': spec['shots'][0]['requires'] = ['warningReturns']
            if edit == 'state': spec['shots'][1]['before']['door'] = 'open'
            if edit == 'speaker': spec['shots'][0]['dialogue'][0]['source'] = 'on_screen'
            with self.subTest(edit=edit), self.assertRaises(ProjectError): validate_spec(spec)

    def test_create_retry_and_conflicting_creation(self):
        self.assertEqual(self.service.create(specification(), 'create-signal')['project_id'], self.pid)
        changed = specification(); changed['title'] = 'Another film'
        with self.assertRaises(ProjectError): self.service.create(changed, 'create-signal')

    def test_lost_response_retry_precedes_revision_check(self):
        request = {'command_id': 'same', 'expected_revision': 1, 'action': 'prepare-assets'}
        first = self.service.command(self.pid, request)
        self.assertEqual(first, self.service.command(self.pid, request))
        self.assertEqual(len(self.get()['commands']), 1)
        with self.assertRaises(ProjectError): self.service.command(self.pid, dict(request, action='cancel'))
        with self.assertRaises(ProjectError): self.service.command(self.pid, dict(request, command_id='other'))

    def test_agent_cannot_approve_any_stage(self):
        for action in ('approve-storyboard', 'review', 'approve-film', 'authorize-retry'):
            with self.subTest(action=action), self.assertRaises(ProjectError) as error: self.command(action)
            self.assertEqual(error.exception.status, 403)

    def test_assembly_and_requests_are_gated_before_approval(self):
        self.prepared()
        for action in ('render-ready', 'assemble'):
            with self.assertRaises(ProjectError): self.command(action)
        self.command('approve-storyboard', human=True)
        with self.assertRaises(ProjectError): self.command('assemble')

    def test_only_ready_shots_get_immutable_gpu_disabled_requests(self):
        self.approve_board(); self.prepare_takes()
        project = self.get()
        self.assertEqual({t['shot_id'] for t in project['takes']}, {'radioWarning', 'jamesChoice'})
        for take in project['takes']:
            path, _ = self.service.artifact(self.pid, take['request_artifact_id'])
            bundle = json.loads(path.read_text())
            self.assertEqual(bundle['gpu_policy'], 'disabled')
            self.assertNotIn('MiniMaxH3AddGuide', {n['class_type'] for n in bundle['graph'].values()})
            self.assertTrue(all('<Video 1>' not in str(n) for n in bundle['graph'].values()))
        self.command('render-ready')
        self.assertEqual(len(self.get()['takes']), 2)
        self.attach_and_approve('radioWarning'); self.command('render-ready')
        self.assertEqual(len(self.get()['takes']), 3)
        self.assertIn('kateRecognition', {t['shot_id'] for t in self.get()['takes']})

    def test_changed_parent_invalidates_descendants_but_preserves_independent_take(self):
        self.approve_board(); self.prepare_takes()
        parent = self.attach_and_approve('radioWarning')
        independent = self.attach_and_approve('jamesChoice')
        self.command('render-ready'); self.attach_and_approve('kateRecognition')
        spec = copy.deepcopy(self.get()['spec']); spec['shots'][0]['prompt'] += ' Tight framing.'
        self.command('update', {'spec': spec})
        project = self.get()
        self.assertEqual(project['approved_takes'], {'jamesChoice': independent['id']})
        self.assertEqual(len(project['reviews']), 3)
        self.assertIn(parent['id'], [t['id'] for t in project['takes']])

    def test_changed_retry_needs_owner_authorization_and_stops_after_two_takes(self):
        self.approve_board(); self.prepare_takes(); self.attach_and_approve('radioWarning')
        spec = copy.deepcopy(self.get()['spec']); spec['shots'][0]['prompt'] += ' A tighter composition.'
        self.command('update', {'spec': spec}); self.approve_board(); self.prepare_takes()
        self.assertTrue(any(b['shot_id'] == 'radioWarning' for b in self.get()['blocked_shots']))
        self.command('authorize-retry', {'shot_id': 'radioWarning', 'note': 'Tighter composition after viewing the first take'}, human=True)
        self.command('render-ready'); self.attach_and_approve('radioWarning')
        spec = copy.deepcopy(self.get()['spec']); spec['shots'][0]['prompt'] += ' Another change.'
        self.command('update', {'spec': spec}); self.approve_board(); self.prepare_takes()
        self.assertIn('Two-take limit', next(b['reason'] for b in self.get()['blocked_shots'] if b['shot_id'] == 'radioWarning'))
        with self.assertRaises(ProjectError):
            self.command('authorize-retry', {'shot_id': 'radioWarning', 'note': 'Third attempt'}, human=True)

    def test_cancellation_survives_restart_and_resume_is_bounded(self):
        self.command('prepare-assets'); self.command('cancel')
        restarted = FilmProjects(self.root / 'projects')
        self.assertTrue(restarted.get(self.pid)['cancelled'])
        self.assertFalse(restarted.tick())
        self.command('resume')
        self.assertEqual(self.get()['commands'][0]['status'], 'queued')

    def test_interrupted_cpu_commands_recover_at_most_twice(self):
        self.command('prepare-assets')
        with self.service.store.transaction() as db:
            db.execute("UPDATE commands SET status='running',attempts=2 WHERE project_id=?", (self.pid,))
        self.assertFalse(self.service.tick())
        self.assertEqual(self.get()['status'], 'failed')
        with self.assertRaises(ProjectError): self.command('resume')
        self.assertEqual(self.get()['commands'][0]['status'], 'failed')

    def test_resume_does_not_replay_an_old_failure_after_a_later_success(self):
        self.command('prepare-assets')
        with patch('local_film.projects.media.prepare', side_effect=ProjectError('original error')): self.service.tick()
        self.prepared(); self.command('cancel'); self.command('resume')
        self.assertFalse(any(c['status'] == 'queued' for c in self.get()['commands']))
        self.assertEqual(self.get()['status'], 'awaiting-storyboard-review')

    def test_resume_cannot_repurpose_an_interrupted_command_for_changed_inputs(self):
        self.command('prepare-assets')
        with patch('local_film.projects.media.prepare', side_effect=ProjectError('original error')): self.service.tick()
        changed = copy.deepcopy(self.get()['spec']); changed['title'] = 'New revision'
        self.command('update', {'spec': changed})
        with self.assertRaises(ProjectError): self.command('resume')

    def test_cancel_during_cpu_work_does_not_publish_partial_artifacts(self):
        self.command('prepare-assets')
        def work(*args, **kwargs):
            self.command('cancel')
            raise ProjectError('cancelled')
        with patch('local_film.projects.media.prepare', side_effect=work): self.service.tick()
        self.assertEqual(self.get()['status'], 'cancelled')
        self.assertEqual(self.get()['artifacts'], [])

    def test_artifact_integrity_and_path_guards(self):
        self.prepared()
        project = self.get(); artifact = project['artifacts'][0]
        path, _ = self.service.artifact(self.pid, artifact['id'])
        path.write_bytes(b'changed after publication')
        with self.assertRaises(ProjectError): self.service.artifact(self.pid, artifact['id'])
        with self.assertRaises(ProjectError): self.service.get('../outside')


    def test_real_http_revision_cors_human_review_and_range(self):
        http = FilmHTTPServer(('127.0.0.1', 0), self.service, ['http://127.0.0.1:33030'])
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor())
        try:
            caps = json.load(opener.open(base + '/api/film/v1/capabilities'))
            self.assertEqual(caps['gpu_policy'], 'disabled')
            prefix = base + '/api/film/v1/projects/' + self.pid
            request = urllib.request.Request(prefix, headers={'Origin': 'https://untrusted.example'})
            with self.assertRaises(urllib.error.HTTPError) as error: opener.open(request)
            self.assertEqual(error.exception.code, 403)
            self.prepared()
            body = {'command_id': 'approve', 'expected_revision': self.get()['revision'], 'action': 'approve-storyboard'}
            req = urllib.request.Request(prefix + '/commands', json.dumps(body).encode(), {'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error: opener.open(req)
            self.assertEqual(error.exception.code, 403)
            page = opener.open(base + self.get()['review_url']).read().decode()
            self.assertIn('Local Film Review', page)
            req = urllib.request.Request(base + '/film/projects/' + self.pid + '/commands', json.dumps(body).encode(),
                {'Content-Type': 'application/json', 'X-Film-Review': http.review_token})
            self.assertEqual(json.load(opener.open(req))['command_status'], 'applied')
            aid = self.get()['artifacts'][0]['id']
            req = urllib.request.Request(prefix + '/artifacts/' + aid, headers={'Range': 'bytes=0-3'})
            response = opener.open(req)
            self.assertEqual(response.status, 206); self.assertEqual(response.read(), b'plan')
        finally:
            http.shutdown(); http.server_close(); thread.join()

    def test_lost_http_response_does_not_cancel_or_duplicate_cpu_work(self):
        http = FilmHTTPServer(('127.0.0.1', 0), self.service)
        handler_errors = []
        http.handle_error = lambda *args: handler_errors.append(args)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        body = json.dumps({'command_id': 'lostReply', 'expected_revision': 1, 'action': 'prepare-assets'}).encode()
        path = '/api/film/v1/projects/' + self.pid + '/commands'
        try:
            with socket.create_connection(('127.0.0.1', http.server_port)) as connection:
                header = f'POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{http.server_port}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n'
                connection.sendall(header.encode() + body)
            for _ in range(100):
                if self.get()['commands']: break
                time.sleep(0.01)
            self.assertEqual(self.get()['commands'][0]['status'], 'queued')
            self.assertFalse(self.get()['cancelled'])
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            request = urllib.request.Request(f'http://127.0.0.1:{http.server_port}' + path, body, {'Content-Type': 'application/json'})
            self.assertEqual(json.load(opener.open(request))['command_status'], 'queued')
            self.assertEqual(len(self.get()['commands']), 1)
        finally:
            http.shutdown(); http.server_close(); thread.join()
        self.assertEqual(handler_errors, [])


if __name__ == '__main__': unittest.main()
