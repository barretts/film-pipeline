"""Explicit opt-in worker for an already running local ComfyUI; CPU launchers never use it.

No service startup/shutdown, model unloading, VRAM inspection or global interrupts.
This module can be exercised with injected transports without touching a GPU.
"""
import argparse
import copy
import json
import math
import os
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from . import pipeline, project_media as media
from .project_contract import ProjectError, attempted_take, digest, gpu_active
from .project_inputs import current_request, execution_inputs

VIDEO_OUTPUTS = {'SaveVideo', 'VHS_VideoCombine'}


def graph_values_hash(graph):
    """Comfy validation may coerce a FLOAT widget from 24 to 24.0 in place.

    Preserve booleans and large integer identity; normalize only exact, safe
    integral floats. The original byte-sensitive graph hash remains recorded.
    """
    def value(item):
        if type(item) is float and math.isfinite(item) and item.is_integer() and abs(item) <= 2**53 - 1:
            return int(item)
        if isinstance(item, dict): return {k: value(v) for k, v in item.items()}
        if isinstance(item, list): return [value(v) for v in item]
        return item
    return digest(value(graph))


class SubmissionRejected(ProjectError):
    """An explicit HTTP client error confirms that this submission was rejected."""


class ComfyTransport:
    def __init__(self, input_root, output_root, origin='http://127.0.0.1:8191', timeout=30):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or
                parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ProjectError('Use an unauthenticated loopback ComfyUI HTTP origin')
        self.origin = origin.rstrip('/')
        self.input_root, self.output_root = Path(input_root).resolve(), Path(output_root).resolve()
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf8')
        request = urllib.request.Request(self.origin + path, data=data, headers={'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=self.timeout) as response:
            return json.loads(response.read(16_000_001))

    def queue(self):
        return self.request('/queue')

    def stage(self, bundle, inputs):
        prefix = f'films/{bundle["project_id"]}/{bundle["take_id"]}/'
        names = set()
        for item in inputs:
            name = item['name']
            relative = PurePosixPath(name)
            target = (self.input_root / name).resolve()
            if (not name.startswith(prefix) or '\\' in name or relative.is_absolute() or
                    '..' in relative.parts or not target.is_relative_to(self.input_root)):
                raise ProjectError('Render input escaped its take namespace')
            source = Path(item['source']).resolve()
            if media.file_hash(source) != item['sha256']:
                raise ProjectError('Render input changed before staging')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if media.file_hash(target) != item['sha256']:
                    raise ProjectError('Existing staged input differs; refusing to overwrite it', 409)
            else:
                partial = target.with_name(uuid.uuid4().hex + '.partial')
                try:
                    with partial.open('xb') as output, source.open('rb') as original:
                        shutil.copyfileobj(original, output); output.flush(); os.fsync(output.fileno())
                    if media.file_hash(partial) != item['sha256']:
                        raise ProjectError('Render input changed during staging')
                    os.link(partial, target)
                finally:
                    partial.unlink(missing_ok=True)
            names.add(name)
        graph = copy.deepcopy(bundle['graph'])
        for node in graph.values():
            if node['class_type'] in ('LoadImage', 'LoadAudio'):
                key = 'image' if node['class_type'] == 'LoadImage' else 'audio'
                if node['inputs'][key] not in names:
                    raise ProjectError('Graph references an unstaged input')
            if node['class_type'] in VIDEO_OUTPUTS and node['inputs']['filename_prefix'] != prefix.rstrip('/'):
                raise ProjectError('Output prefix escaped its take namespace')
        return graph

    def submit(self, graph, record):
        try:
            response = self.request('/prompt', {'prompt': graph, 'prompt_id': record['prompt_id'],
                'client_id': record['client_id'], 'extra_data': record['ownership']})
        except urllib.error.HTTPError as error:
            if 400 <= error.code < 500:
                raise SubmissionRejected('ComfyUI rejected submission: ' + error.read(2000).decode('utf8', errors='replace')) from error
            raise
        if response.get('prompt_id') != record['prompt_id']:
            raise ProjectError('Server did not echo the reserved prompt UUID; reconcile before further work', 409)
        return response

    @staticmethod
    def _owned(entry, record):
        if not isinstance(entry, (list, tuple)) or len(entry) < 4 or entry[1] != record['prompt_id']:
            raise ProjectError('Prompt identity could not be verified', 409)
        extra = entry[3]
        expected = dict(record['ownership'], client_id=record['client_id'])
        if not isinstance(extra, dict) or any(extra.get(k) != v for k, v in expected.items()):
            raise ProjectError('Prompt belongs to a different client or take; refusing to act on it', 409)
        if (digest(entry[2]) != record['graph_hash'] and
                (not record.get('graph_values_hash') or graph_values_hash(entry[2]) != record['graph_values_hash'])):
            raise ProjectError('Prompt graph differs from the reserved request', 409)

    def observe(self, record):
        queue = self.queue()
        for key, state in (('queue_running', 'running'), ('queue_pending', 'queued')):
            for item in queue.get(key, []):
                if len(item) > 1 and item[1] == record['prompt_id']:
                    self._owned(item, record)
                    return {'state': state}
        history = self.request('/history/' + record['prompt_id']).get(record['prompt_id'])
        if history is None:
            return {'state': 'absent'}
        self._owned(history.get('prompt'), record)
        status = history.get('status', {})
        if status.get('status_str') == 'error':
            return {'state': 'failed', 'history': history}
        if status.get('completed') and status.get('status_str') == 'success':
            return {'state': 'complete', 'history': history}
        raise ProjectError('History is not a recognized terminal result; reconcile manually', 409)

    def cancel(self, record):
        # This route uses interrupt_if_running(prompt_id) atomically. A global
        # /interrupt call, or a check followed by a global interrupt, is unsafe.
        return self.request('/api/jobs/' + record['prompt_id'] + '/cancel', {})

    def output(self, observation, bundle):
        outputs = observation['history'].get('outputs', {})
        prefix = f'films/{bundle["project_id"]}'
        namespace = (self.output_root / prefix).resolve()
        found = set()
        for node_id, node in bundle['graph'].items():
            if node['class_type'] not in VIDEO_OUTPUTS:
                continue
            for key in ('images', 'videos', 'gifs'):
                for item in outputs.get(node_id, {}).get(key, []):
                    filename = item.get('filename', '')
                    if Path(filename).suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv'):
                        continue  # Some video nodes also return a still preview.
                    path = (self.output_root / item.get('subfolder', '') / filename).resolve()
                    if (item.get('type', 'output') != 'output' or not path.is_relative_to(namespace) or
                            not filename.startswith(bundle['take_id'] + '_') or
                            Path(filename).name != filename or '\\' in filename or
                            path.suffix.lower() not in ('.mp4', '.mov', '.webm', '.mkv')):
                        raise ProjectError('History output escaped its take namespace', 409)
                    if path.is_file():
                        found.add(path)
        if len(found) != 1:
            raise ProjectError('History needs exactly one available take video; no resubmission will occur', 409)
        return found.pop()


class GpuWorker:
    def __init__(self, projects, transport=None, *, enabled=False, lock_root=None,
                 clock=time.monotonic, sleep=time.sleep, stop=None):
        self.projects, self.transport, self.enabled = projects, transport, enabled
        self.lock_root = Path(lock_root) if lock_root is not None else pipeline.JOBS
        self.clock, self.sleep = clock, sleep
        self.stop = stop if stop is not None else threading.Event()

    def _change(self, project_id, take_id, state, error=None, **values):
        with self.projects.store.transaction() as db:
            project = self.projects.store.read(db, project_id)
            take = next(t for t in project['takes'] if t['id'] == take_id)
            take.setdefault('gpu', {}).update(values, state=state, error=error)
            take['status'] = state
            project['status'] = ('cancelled' if project['cancelled'] and not any(gpu_active(t) for t in project['takes']) else
                                 'cancel-pending' if project['cancelled'] else state)
            project['revision'] += 1
            self.projects.store.save(db, project)
        return project, take

    def run_one(self, project_id, take_id, *, timeout=900, poll_seconds=2, cancel_timeout=30):
        if not self.enabled:
            return {'state': 'disabled', 'submitted': False}
        if (self.transport is None or any(not math.isfinite(value) for value in (timeout, poll_seconds, cancel_timeout)) or
                timeout <= 0 or poll_seconds <= 0 or cancel_timeout < 0):
            raise ProjectError('Opt-in worker needs a transport and positive bounded timeouts')
        with pipeline.locked(self.lock_root / 'pipeline.lock'), pipeline.locked(self.lock_root / 'gpu.lock'):
            # The same reservation wins after a worker restart. A lost response
            # must never turn into a second prompt, even for another project.
            for other in self.projects.store.list():
                for candidate in other['takes']:
                    if gpu_active(candidate) and (other['project_id'], candidate['id']) != (project_id, take_id):
                        raise ProjectError('Another GPU request needs reconciliation before dispatch', 409)
            return self._run(project_id, take_id, timeout, poll_seconds, cancel_timeout)

    def _run(self, project_id, take_id, timeout, poll, cancel_timeout):
        service = self.projects
        with service.store.transaction() as db:
            project = service.store.read(db, project_id)
            take = next((t for t in project['takes'] if t['id'] == take_id), None)
            if take is None:
                raise ProjectError('Take not found', 404)
            record = take.get('gpu', {})
            if take.get('artifact_id') or (attempted_take(take) and not gpu_active(take)):
                return {'state': record.get('state', 'complete'), 'submitted': False}
            if db.execute("SELECT 1 FROM commands WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchone():
                raise ProjectError('Finish or cancel CPU work before GPU dispatch', 409)
            if record.get('submitted_at') and not record.get('graph_values_hash'):
                path, _ = service._artifact(project, record['manifest_artifact_id'])
                saved = json.loads(path.read_text(encoding='utf8'))['graph']
                if digest(saved) != record['graph_hash']:
                    raise ProjectError('Saved submission graph changed; refusing recovery', 409)
                record['graph_values_hash'] = graph_values_hash(saved)
                project['revision'] += 1
                service.store.save(db, project)
            if not record.get('submitted_at'):
                if project['cancelled'] or self.stop.is_set():
                    if gpu_active(take):
                        take['gpu'].update(state='cancelled')
                        project.update(status='cancelled' if project['cancelled'] else 'awaiting-gpu',
                                       revision=project['revision'] + 1)
                        service.store.save(db, project)
                    return {'state': 'cancelled', 'submitted': False}
                take, bundle = current_request(service, project, take_id)
                inputs = execution_inputs(service, project, take, bundle)
                take['gpu'] = {'state': 'preparing', 'service_changes': 'none'}
                project.update(status='preparing-gpu', revision=project['revision'] + 1)
                service.store.save(db, project)
        if not record.get('submitted_at'):
            try:
                queue = self.transport.queue()
                if queue.get('queue_running') or queue.get('queue_pending'):
                    raise ProjectError('ComfyUI queue is occupied; no services or foreign work were changed', 409)
                graph = self.transport.stage(bundle, inputs)
                record = {'prompt_id': str(uuid.uuid4()), 'client_id': 'film-' + uuid.uuid4().hex,
                    'ownership': {'film_project_id': project_id, 'film_take_id': take_id},
                    'graph_hash': digest(graph), 'graph_values_hash': graph_values_hash(graph),
                    'submitted_at': time.time(), 'seen': False,
                    'service_changes': 'none', 'cancel_requested': False}
                with service.store.transaction() as db:
                    current = service.store.read(db, project_id)
                    current_take, _ = current_request(service, current, take_id)
                    if current['cancelled'] or self.stop.is_set():
                        current_take['gpu'] = {'state': 'cancelled', 'service_changes': 'none'}
                        current.update(status='cancelled', revision=current['revision'] + 1)
                        service.store.save(db, current)
                        return {'state': 'cancelled', 'submitted': False}
                    manifest = service.store.directory(project_id) / 'takes' / take_id / ('submission-' + record['prompt_id'] + '.json')
                    with manifest.open('x', encoding='utf8') as output:
                        json.dump(dict(record, graph=graph, inputs=inputs), output, indent=2)
                        output.flush(); os.fsync(output.fileno())
                    record['manifest_artifact_id'] = service._register_files(current, [manifest])[str(manifest.resolve())]
                    current_take['gpu'] = dict(record, state='submitting')
                    current.update(status='submitting', revision=current['revision'] + 1)
                    service.store.save(db, current)
            except Exception as error:
                self._change(project_id, take_id, 'preflight-failed', str(error))
                return {'state': 'preflight-failed', 'submitted': False, 'error': str(error)}
            # A process loss from this commit onward is ambiguous, including
            # between commit and POST. Recovery only observes the saved UUID.
            try:
                self.transport.submit(graph, record)
                self._change(project_id, take_id, 'queued')
            except SubmissionRejected as error:
                self._change(project_id, take_id, 'rejected', str(error))
                return {'state': 'rejected', 'submitted': True, 'error': str(error)}
            except Exception as error:
                self._change(project_id, take_id, 'submission-unknown', str(error))
                return {'state': 'submission-unknown', 'submitted': True, 'error': str(error)}
        started, cancelling_at = self.clock(), None
        while True:
            project = service.store.get(project_id)
            take = next(t for t in project['takes'] if t['id'] == take_id)
            record = take['gpu']
            cancel = project['cancelled'] or record.get('cancel_requested') or self.stop.is_set() or self.clock() - started >= timeout
            if cancel and cancelling_at is None:
                cancelling_at = self.clock()
                reason = 'project-cancel' if project['cancelled'] else 'worker-stop' if self.stop.is_set() else 'timeout'
                self._change(project_id, take_id, 'cancel-pending', cancel_requested=True, cancel_reason=reason)
            try:
                observed = ({'state': 'complete', 'history': record['history']}
                            if record['state'] == 'output-pending' and record.get('history')
                            else self.transport.observe(record))
                state = observed['state']
                if state == 'absent':
                    if cancel and record.get('cancel_sent') and record.get('seen'):
                        self._change(project_id, take_id, 'cancelled')
                        return {'state': 'cancelled', 'submitted': True}
                    self._change(project_id, take_id, 'cancel-pending' if cancel else 'submission-unknown',
                                 'Reserved prompt is absent; inspect server history/logs. It was not resubmitted.')
                    return {'state': 'cancel-pending' if cancel else 'submission-unknown', 'submitted': True}
                if state in ('complete', 'failed'):
                    if cancel or state == 'failed':
                        terminal = 'cancelled' if cancel else 'failed'
                        self._change(project_id, take_id, terminal,
                                     None if cancel else 'ComfyUI execution failed; inspect its history', history=observed.get('history'))
                        return {'state': terminal, 'submitted': True}
                    self._change(project_id, take_id, 'output-pending', seen=True, history=observed['history'])
                    current = service.store.get(project_id)
                    _, bundle = current_request(service, current, take_id)
                    path = self.transport.output(observed, bundle)
                    fresh = service.store.get(project_id)
                    service.import_take(project_id, take_id, path, fresh['revision'], _gpu_prompt=record['prompt_id'])
                    return {'state': 'awaiting-review', 'submitted': True}
                if state not in ('queued', 'running'):
                    raise ProjectError('Unrecognized transport state; refusing further dispatch', 409)
                self._change(project_id, take_id, 'cancel-pending' if cancel else state, seen=True)
                if cancel:
                    # Ownership was checked in this observation. The route is
                    # atomic and ID-specific, so a queue race cannot hit others.
                    self.transport.cancel(record)
                    self._change(project_id, take_id, 'cancel-pending', cancel_sent=True, seen=True)
                    if self.clock() - cancelling_at >= cancel_timeout:
                        return {'state': 'cancel-pending', 'submitted': True}
                self.sleep(poll)
            except Exception as error:
                # Preserve the reservation and attempt budget after network,
                # output-copy, validation or ownership failures.
                fresh = service.store.get(project_id)
                current = next(t for t in fresh['takes'] if t['id'] == take_id)['gpu']['state']
                state = 'cancel-pending' if cancel else 'output-pending' if current == 'output-pending' else 'recovery-blocked'
                self._change(project_id, take_id, state, str(error))
                return {'state': state, 'submitted': True, 'error': str(error)}


def main():
    from .projects import FilmProjects, ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_id'); parser.add_argument('take_id')
    parser.add_argument('--root', type=Path, default=ROOT / 'film-projects')
    parser.add_argument('--enable-gpu', action='store_true', help='Explicitly authorize submission to an existing local GPU server')
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--origin', default='http://127.0.0.1:8191')
    parser.add_argument('--timeout', type=float, default=900)
    args = parser.parse_args()
    if not args.enable_gpu:
        parser.error('GPU execution is disabled; this separate worker requires --enable-gpu')
    stop = threading.Event()
    import signal
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    worker = GpuWorker(FilmProjects(args.root), ComfyTransport(args.input_root, args.output_root, args.origin),
                       enabled=True, stop=stop)
    print(json.dumps(worker.run_one(args.project_id, args.take_id, timeout=args.timeout), indent=2))


if __name__ == '__main__':
    main()
