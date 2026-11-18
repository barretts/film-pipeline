"""Durable CPU film workflow. This module has no GPU transport or lifecycle calls."""
import copy
import json
import mimetypes
import math
import shutil
import threading
import time
import uuid
from pathlib import Path
from . import project_media as media
from .project_contract import ProjectError, approved_takes, attempted_take, digest, gpu_active, identifier, take_key, validate_spec
from .project_store import ProjectStore
from .project_graphs import request_bundle
from .pipeline import locked, extract_tail, JobError

ROOT = Path(__file__).resolve().parent.parent
ASYNC = {'prepare-assets', 'assemble', 'draft'}
HUMAN = {'approve-storyboard', 'approve-inputs', 'review', 'approve-film', 'authorize-retry'}
AGENT_ACTIONS = {'update', 'prepare-assets', 'render-ready', 'assemble', 'cancel', 'resume', 'draft'}


class FilmProjects:
    def __init__(self, root=ROOT / 'film-projects', registry=ROOT / 'series'):
        self.store = ProjectStore(root)
        self.registry = Path(registry)
        self.wake = threading.Event()
        self.stop = threading.Event()

    def create(self, spec, creation_id):
        spec = validate_spec(spec)
        for character in spec['characters']:
            if not (self.registry / 'characters' / character / 'character.json').is_file():
                raise ProjectError(f'Character is not registered: {character}')
        return self.store.create(spec, creation_id)

    def get(self, project_id):
        project = self.store.get(project_id)
        accepted = approved_takes(project)
        project['approved_takes'] = {s: t['id'] for s, t in accepted.items()}
        project['gpu_active'] = any(gpu_active(t) for t in project['takes'])
        shots = {s['id']: s for s in project['spec']['shots']}
        for take in project['takes']:
            shot = shots.get(take['shot_id'])
            current = shot and all(d in accepted for d in shot['requires']) and take['input_hash'] == take_key(project, shot, accepted)
            reviews = [r for r in project['reviews'] if r['take_id'] == take['id']]
            take['current_inputs'] = bool(current)
            if not current:
                take['status'] = 'stale-inputs'
            elif reviews:
                take['status'] = 'approved' if reviews[-1]['decision'] == 'approve' else 'rejected'
        project['ready_shots'] = [s['id'] for s in project['spec']['shots']
                                  if s['id'] not in accepted and all(d in accepted for d in s['requires'])]
        with self.store.transaction() as db:
            project['commands'] = [dict(r) for r in db.execute(
                'SELECT id,action,status,attempts,error FROM commands WHERE project_id=? ORDER BY created', (project_id,))]
        project['review_url'] = f'/film/projects/{project_id}/review'
        project['preparation_current'] = bool(self._prepared(project))
        project['film_current'] = (project.get('assembly_spec_hash') == digest(project['spec']) and
                                   project.get('assembly_take_ids') == project['approved_takes'] and
                                   len(accepted) == len(project['spec']['shots']))
        return project

    def command(self, project_id, request, human=False):
        if not isinstance(request, dict):
            raise ProjectError('Command must be an object')
        cid = identifier(request.get('command_id'), 'command id')
        action = request.get('action')
        if action not in ASYNC | HUMAN | AGENT_ACTIONS:
            raise ProjectError('Unknown film command')
        if action in HUMAN and not human:
            raise ProjectError('Use the local human review page for approval', 403)
        payload = request.get('payload', {})
        if not isinstance(payload, dict):
            raise ProjectError('Command payload must be an object')
        fingerprint = digest(request)
        with self.store.transaction() as db:
            known = db.execute('SELECT * FROM commands WHERE project_id=? AND id=?', (project_id, cid)).fetchone()
            if known:
                if known['fingerprint'] != fingerprint:
                    raise ProjectError('Command id was already used for a different request', 409)
                return json.loads(known['response'])
            project = self.store.read(db, project_id)
            if type(request.get('expected_revision')) is not int or request['expected_revision'] != project['revision']:
                raise ProjectError('Project changed; refresh before submitting this command', 409)
            active = db.execute("SELECT id,status FROM commands WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchall()
            if active and action not in ('cancel',):
                raise ProjectError('A CPU command is still active; wait or cancel it first', 409)
            if any(gpu_active(t) for t in project['takes']) and action != 'cancel':
                raise ProjectError('An owned GPU request still needs completion or reconciliation; only cancellation is allowed', 409)
            if project['cancelled'] and action not in ('resume', 'cancel'):
                raise ProjectError('Project is cancelled; resume it before making changes', 409)
            if action == 'update':
                spec = validate_spec(payload.get('spec'))
                for character in spec['characters']:
                    if not (self.registry / 'characters' / character / 'character.json').is_file():
                        raise ProjectError(f'Character is not registered: {character}')
                project.update(spec=spec, storyboard_approval=None, status='draft')
            elif action == 'cancel':
                pending = any(gpu_active(t) for t in project['takes']) or any(c['status'] == 'running' for c in active)
                project.update(cancelled=True, status='cancel-pending' if pending else 'cancelled')
                for take in project['takes']:
                    if gpu_active(take):
                        take['gpu']['cancel_requested'] = True
                db.execute("UPDATE commands SET status='cancelled' WHERE project_id=? AND status='queued'", (project_id,))
            elif action == 'resume':
                phase = ('awaiting-storyboard-review' if self._prepared(project) else 'draft')
                if self._prepared(project) and project.get('storyboard_approval'):
                    phase = 'storyboard-approved'
                project.update(cancelled=False, status=phase)
                failed = db.execute("SELECT * FROM commands WHERE project_id=? AND action IN ('prepare-assets','assemble','draft') ORDER BY created DESC LIMIT 1", (project_id,)).fetchone()
                if failed and failed['status'] in ('failed', 'cancelled'):
                    if failed['attempts'] >= 2:
                        raise ProjectError('CPU recovery limit reached; inspect the error and queue a fresh command after changing the relevant condition', 409)
                    if failed['spec_hash'] != digest(project['spec']):
                        raise ProjectError('Interrupted command belongs to different or legacy inputs; queue a fresh command for this revision', 409)
                    db.execute("UPDATE commands SET status='queued',error=NULL WHERE project_id=? AND id=?", (project_id, failed['id']))
                    project['status'] = 'queued'
            elif action == 'approve-storyboard':
                self._require_prepared(project)
                project['storyboard_approval'] = {'spec_hash': digest(project['spec']),
                                                 'preparation_id': project['preparation']['id'], 'time': time.time()}
                project['status'] = 'storyboard-approved'
            elif action == 'render-ready':
                self._require_storyboard(project)
                self._render_ready(project)
            elif action == 'approve-inputs':
                from .project_inputs import approval_key, current_request, execution_inputs
                take, bundle = current_request(self, project, payload.get('take_id'))
                if attempted_take(take):
                    raise ProjectError('Submitted take inputs are immutable', 409)
                execution_inputs(self, project, take, bundle, require_approval=False)
                take['input_approval'] = {'key': approval_key(take), 'time': time.time()}
            elif action == 'authorize-retry':
                self._require_storyboard(project)
                shot = next((s for s in project['spec']['shots'] if s['id'] == payload.get('shot_id')), None)
                if not shot or not str(payload.get('note', '')).strip():
                    raise ProjectError('Retry authorization needs a current shot and a concrete change note')
                rendered = [t for t in project['takes'] if t['shot_id'] == shot['id'] and attempted_take(t)]
                key = take_key(project, shot, approved_takes(project))
                if len(rendered) != 1 or any(t['input_hash'] == key for t in rendered):
                    raise ProjectError('One changed retry is allowed after a rendered take; revise its inputs and review the new storyboard first')
                project.setdefault('retry_authorizations', []).append({'shot_id': shot['id'], 'input_hash': key,
                    'note': payload['note'], 'time': time.time()})
            elif action == 'review':
                self._require_storyboard(project)
                take = next((t for t in project['takes'] if t['id'] == payload.get('take_id')), None)
                if not take or not take.get('artifact_id'):
                    raise ProjectError('Review needs an imported take with a video artifact')
                shot = next((s for s in project['spec']['shots'] if s['id'] == take['shot_id']), None)
                if shot is None:
                    raise ProjectError('Take belongs to a shot removed from this revision', 409)
                accepted = approved_takes(project)
                if take['input_hash'] != take_key(project, shot, accepted):
                    raise ProjectError('Take inputs are stale; prepare a take from the current inputs', 409)
                decision = payload.get('decision')
                if decision not in ('approve', 'reject'):
                    raise ProjectError('Review decision must be approve or reject')
                self._artifact(project, take['artifact_id'])
                project['reviews'].append({'id': str(uuid.uuid4()), 'take_id': take['id'], 'decision': decision,
                                           'note': str(payload.get('note', '')), 'time': time.time()})
                project['status'] = 'ready-to-assemble' if len(approved_takes(project)) == len(project['spec']['shots']) else 'awaiting-review'
            elif action == 'approve-film':
                self._require_storyboard(project)
                current_takes = {s: t['id'] for s, t in approved_takes(project).items()}
                if (project.get('assembly_spec_hash') != digest(project['spec']) or not project.get('film_artifact_id') or
                        project.get('assembly_take_ids') != current_takes or len(current_takes) != len(project['spec']['shots'])):
                    raise ProjectError('Assemble the current approved shots before final review')
                self._artifact(project, project['film_artifact_id'])
                project['status'] = 'complete'
                project['film_approval'] = {'artifact_id': project['film_artifact_id'], 'time': time.time()}
            elif action == 'assemble':
                self._require_storyboard(project)
                if len(approved_takes(project)) != len(project['spec']['shots']):
                    raise ProjectError('Every current shot needs an approved take before assembly')
            project['revision'] += 1
            if action in ASYNC:
                project['status'] = 'queued'
            response = {'project_id': project_id, 'revision': project['revision'], 'command_id': cid,
                        'command_status': 'queued' if action in ASYNC else 'applied'}
            self.store.save(db, project)
            db.execute('INSERT INTO commands(project_id,id,fingerprint,action,payload,status,created,response,spec_hash) VALUES(?,?,?,?,?,?,?,?,?)',
                       (project_id, cid, fingerprint, action, json.dumps(payload), response['command_status'], time.time(), json.dumps(response), digest(project['spec'])))
        self.wake.set()
        return response

    def _prepared(self, project):
        return project.get('preparation') and project['preparation']['spec_hash'] == digest(project['spec'])

    def _require_prepared(self, project):
        if not self._prepared(project):
            raise ProjectError('Prepare assets and review the timed animatic for this revision first')
        base = self.store.directory(project['project_id']).resolve()
        for shot in project['preparation']['shots'].values():
            for key, hash_key in (('audio', 'audio_hash'), ('conditioning_audio', 'conditioning_hash')):
                if key not in shot:
                    continue
                path = Path(shot[key]).resolve()
                if not path.is_relative_to(base) or not path.is_file() or media.file_hash(path) != shot[hash_key]:
                    raise ProjectError('Prepared audio changed or is missing; prepare a new revision', 409)
        self._artifact(project, project['preparation']['animatic_artifact_id'])

    def _require_storyboard(self, project):
        self._require_prepared(project)
        approval = project.get('storyboard_approval') or {}
        if (approval.get('spec_hash') != digest(project['spec']) or
                approval.get('preparation_id') != project['preparation']['id']):
            raise ProjectError('The current storyboard and animatic require human approval', 409)

    def _register_files(self, project, files):
        registered = {}
        base = self.store.directory(project['project_id']).resolve()
        for filename in files:
            path = Path(filename).resolve()
            if not path.is_relative_to(base) or not path.is_file():
                raise ProjectError('Artifact escaped its project directory')
            record = {'id': 'art-' + uuid.uuid4().hex, 'path': path.relative_to(base).as_posix(),
                      'sha256': media.file_hash(path), 'bytes': path.stat().st_size,
                      'media_type': mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}
            project['artifacts'].append(record)
            registered[str(path)] = record['id']
        return registered

    def artifact(self, project_id, artifact_id):
        project = self.store.get(project_id)
        return self._artifact(project, artifact_id)

    def _artifact(self, project, artifact_id):
        item = next((a for a in project['artifacts'] if a['id'] == artifact_id), None)
        if item is None:
            raise ProjectError('Artifact not found', 404)
        base = self.store.directory(project['project_id']).resolve()
        path = (base / item['path']).resolve()
        if not path.is_relative_to(base) or not path.is_file():
            raise ProjectError('Artifact is missing or outside the project', 409)
        if media.file_hash(path) != item['sha256']:
            raise ProjectError('Artifact changed after publication; refusing to serve it', 409)
        return path, item

    def _render_ready(self, project):
        accepted = approved_takes(project)
        if len(accepted) == len(project['spec']['shots']):
            project.update(status='ready-to-assemble', blocked_shots=[])
            return
        for take in accepted.values():
            self._artifact(project, take['artifact_id'])
            if take.get('end_frame'):
                self._artifact(project, take['end_frame']['artifact_id'])
        blocked, pending_review = [], False
        for shot in project['spec']['shots']:
            if shot['id'] in accepted or any(d not in accepted for d in shot['requires']):
                continue
            key = take_key(project, shot, accepted)
            rendered = [t for t in project['takes'] if t['shot_id'] == shot['id'] and attempted_take(t)]
            existing = next((t for t in reversed(project['takes']) if t['shot_id'] == shot['id'] and t['input_hash'] == key), None)
            if existing:
                reviews = [r for r in project['reviews'] if r['take_id'] == existing['id']]
                if existing.get('artifact_id') and (not reviews or reviews[-1]['decision'] != 'reject'):
                    pending_review = True
                elif attempted_take(existing):
                    reason = ('Two-take limit reached; owner must revise the approach' if len(rendered) >= 2 else
                              'These inputs were already attempted; revise them and obtain owner retry authorization')
                    blocked.append({'shot_id': shot['id'], 'reason': reason})
                continue  # Resuming or double-clicking never creates another take.
            if len(rendered) >= 2:
                blocked.append({'shot_id': shot['id'], 'reason': 'Two-take limit reached; owner must revise the approach'}); continue
            if rendered and not any(a['shot_id'] == shot['id'] and a['input_hash'] == key for a in project.get('retry_authorizations', [])):
                blocked.append({'shot_id': shot['id'], 'reason': 'One changed retry needs owner authorization on the review page'}); continue
            take = {'id': 'take-' + uuid.uuid4().hex, 'shot_id': shot['id'], 'input_hash': key,
                    'status': 'awaiting-gpu', 'created': time.time(), 'artifact_id': None,
                    'dependency_takes': {d: accepted[d]['id'] for d in shot['requires']}}
            bundle = request_bundle(project, shot, take)
            folder = self.store.directory(project['project_id']) / 'takes' / take['id']
            folder.mkdir(parents=True, exist_ok=False)
            path = folder / 'request.json'
            path.write_text(json.dumps(bundle, indent=2), encoding='utf8')
            take['request_artifact_id'] = self._register_files(project, [path])[str(path.resolve())]
            project['takes'].append(take)
        project['blocked_shots'] = blocked
        project['status'] = 'awaiting-owner-decision' if blocked else 'awaiting-review' if pending_review else 'awaiting-gpu'

    def import_take(self, project_id, take_id, filename, expected_revision, *, _gpu_prompt=None):
        """Operator CLI only; HTTP/agent interfaces cannot read arbitrary local paths."""
        with self.store.transaction() as db:
            project = self.store.read(db, project_id)
            if project['revision'] != expected_revision:
                raise ProjectError('Project changed; refresh before importing', 409)
            if project['cancelled']:
                raise ProjectError('A cancelled project cannot import new media', 409)
            active = [t for t in project['takes'] if gpu_active(t)]
            if active and not (len(active) == 1 and active[0]['id'] == take_id and _gpu_prompt and
                               active[0]['gpu']['state'] == 'output-pending' and
                               active[0]['gpu']['prompt_id'] == _gpu_prompt):
                raise ProjectError('Reconcile the active GPU request before importing media', 409)
            self._require_storyboard(project)
            take = next((t for t in project['takes'] if t['id'] == take_id), None)
            if not take or take.get('artifact_id'):
                raise ProjectError('Take is missing or already has immutable media', 409)
            shot = next((s for s in project['spec']['shots'] if s['id'] == take['shot_id']), None)
            if not shot or take['input_hash'] != take_key(project, shot, approved_takes(project)):
                raise ProjectError('Take inputs changed; prepare a current request before importing', 409)
            source = Path(filename).resolve()
            if source.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm') or not source.is_file():
                raise ProjectError('Import needs an existing local video')
            # Validation precedes publication, and does not inspect any GPU endpoint.
            source_hash = media.file_hash(source)
            info = media.probe(source)
            video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            if video is None:
                raise ProjectError('Imported take has no video stream')
            duration = float(video.get('duration') or info.get('format', {}).get('duration', 0))
            if not math.isfinite(duration) or duration < shot['seconds'] - 1 / 24:
                raise ProjectError('Imported video is shorter than its approved shot')
            media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-threads', '2', '-i', source,
                           '-map', '0:v:0', '-f', 'null', '-'])
            directory = self.store.directory(project_id) / 'takes' / take_id
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / ('video' + source.suffix.lower())
            if target.exists():
                if media.file_hash(target) != source_hash:
                    raise ProjectError('Existing unpublished take differs; inspect it before retrying', 409)
            else:
                import os
                partial = directory / ('import-' + uuid.uuid4().hex + '.partial')
                with partial.open('xb') as output, source.open('rb') as original:
                    shutil.copyfileobj(original, output)
                    output.flush(); os.fsync(output.fileno())
                if media.file_hash(partial) != source_hash:
                    partial.unlink()
                    raise ProjectError('Source video changed during validation/import', 409)
                os.link(partial, target)
                partial.unlink()
            tail = directory / 'end-frame.png'
            extract_tail(target, tail)
            registered = self._register_files(project, [target, tail])
            take.update(artifact_id=registered[str(target.resolve())], status='awaiting-review')
            take['validation'] = {'full_video_decode': True, 'seconds': duration, 'human_review': 'pending'}
            if _gpu_prompt:
                take['gpu'].update(state='complete', completed_at=time.time())
            take['end_frame'] = {'artifact_id': registered[str(tail.resolve())], 'path': str(tail), 'sha256': media.file_hash(tail)}
            project.update(status='awaiting-review', revision=project['revision'] + 1)
            self.store.save(db, project)
        return self.get(project_id)

    def tick(self):
        try:
            with locked(self.store.root / 'cpu-worker.lock'):
                return self._tick()
        except JobError:
            return False

    def _tick(self):
        with self.store.transaction() as db:
            # Holding the OS lock proves that a previous running command lost its worker.
            for old in db.execute("SELECT * FROM commands WHERE status='running'").fetchall():
                status = 'queued' if old['attempts'] < 2 else 'failed'
                db.execute('UPDATE commands SET status=?,error=? WHERE project_id=? AND id=?',
                           (status, 'Interrupted CPU command; bounded recovery', old['project_id'], old['id']))
                if status == 'failed':
                    failed = self.store.read(db, old['project_id'])
                    failed.update(status='failed', revision=failed['revision'] + 1)
                    self.store.save(db, failed)
            row = db.execute("SELECT * FROM commands WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if row is None:
                return False
            project_id, cid, action = row['project_id'], row['id'], row['action']
            project = self.store.read(db, project_id)
            if row['spec_hash'] != digest(project['spec']):
                db.execute("UPDATE commands SET status='failed',error='Inputs changed or legacy command: queue a fresh command' WHERE project_id=? AND id=?", (project_id, cid))
                project.update(status='failed', revision=project['revision'] + 1)
                self.store.save(db, project)
                return True
            if project['cancelled']:
                db.execute("UPDATE commands SET status='cancelled' WHERE project_id=? AND id=?", (project_id, cid))
                return True
            db.execute("UPDATE commands SET status='running',attempts=attempts+1 WHERE project_id=? AND id=?", (project_id, cid))
            project.update(status='preparing' if action == 'prepare-assets' else action, revision=project['revision'] + 1)
            self.store.save(db, project)
            attempt = row['attempts'] + 1
        directory = self.store.directory(project_id) / 'commands' / cid / f'attempt-{attempt}'
        cancelled = lambda: self.store.get(project_id)['cancelled'] or self.stop.is_set()
        try:
            if action == 'prepare-assets':
                result = media.prepare(project, directory, self.registry, cancelled,
                                       voice_cache_dir=self.store.directory(project_id) / 'voice-cache')
            elif action == 'assemble':
                accepted = approved_takes(project)
                paths = {s: self.artifact(project_id, t['artifact_id'])[0] for s, t in accepted.items()}
                result = media.assemble(project, directory, paths, cancelled)
            elif action == 'draft':
                from .project_writer import draft
                result = {'spec': draft(project, json.loads(row['payload']), directory, cancelled), 'files': []}
            else:
                raise ProjectError('Unknown CPU work type')
            with self.store.transaction() as db:
                current = self.store.read(db, project_id)
                if current['cancelled']:
                    raise ProjectError('CPU command cancelled', 409)
                registered = self._register_files(current, result['files'])
                if action == 'prepare-assets':
                    preparation = result['preparation']
                    preparation['id'] = cid
                    preparation['animatic_artifact_id'] = registered[str(Path(result['primary']).resolve())]
                    for shot in preparation['shots'].values():
                        shot['card_artifact_id'] = registered[str(Path(shot['card']).resolve())]
                    current.update(preparation=preparation, storyboard_approval=None, status='awaiting-storyboard-review')
                elif action == 'assemble':
                    current.update(film_artifact_id=registered[str(Path(result['primary']).resolve())],
                                   assembly_spec_hash=digest(current['spec']),
                                   assembly_take_ids={s: t['id'] for s, t in approved_takes(current).items()},
                                   status='awaiting-film-review')
                else:
                    current.update(spec=result['spec'], storyboard_approval=None, status='draft')
                current['revision'] += 1
                self.store.save(db, current)
                db.execute("UPDATE commands SET status='complete',error=NULL WHERE project_id=? AND id=?", (project_id, cid))
        except Exception as error:
            with self.store.transaction() as db:
                current = self.store.read(db, project_id)
                status = ('cancelled' if current['cancelled'] else
                          'queued' if self.stop.is_set() and attempt < 2 else 'failed')
                current.update(status=status, revision=current['revision'] + 1)
                self.store.save(db, current)
                db.execute('UPDATE commands SET status=?,error=? WHERE project_id=? AND id=?',
                           (status, str(error), project_id, cid))
        return True

    def serve(self):
        while not self.stop.is_set():
            self.tick()
            self.wake.wait(1)
            self.wake.clear()
