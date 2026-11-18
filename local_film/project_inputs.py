"""Immutable local image bindings and their human review, without inference."""
import json
import os
import shutil
import uuid
from pathlib import Path
from PIL import Image
from . import project_media as media
from .project_contract import ProjectError, approved_takes, digest, gpu_active, take_key

REVIEWED_KINDS = {'composed-first-frame', 'room-reference'}


def current_request(service, project, take_id):
    service._require_storyboard(project)
    take = next((t for t in project['takes'] if t['id'] == take_id), None)
    shot = next((s for s in project['spec']['shots'] if take and s['id'] == take['shot_id']), None)
    accepted = approved_takes(project)
    if not shot or any(d not in accepted for d in shot['requires']) or take['input_hash'] != take_key(project, shot, accepted):
        raise ProjectError('Take inputs are stale; prepare a current request first', 409)
    path, _ = service._artifact(project, take['request_artifact_id'])
    return take, json.loads(path.read_text(encoding='utf8'))


def approval_key(take):
    return digest({'request': take['request_artifact_id'], 'inputs': take.get('input_bindings', {}),
                   'input_hash': take['input_hash']})


def bind_image(service, project_id, take_id, name, filename, expected_revision):
    """Operator-only file import. Binding is preparation; it grants no GPU permission."""
    with service.store.transaction() as db:
        project = service.store.read(db, project_id)
        if project['revision'] != expected_revision:
            raise ProjectError('Project changed; refresh before binding an image', 409)
        if project['cancelled'] or any(gpu_active(t) for t in project['takes']):
            raise ProjectError('Resume or finish active work before binding inputs', 409)
        take, bundle = current_request(service, project, take_id)
        if take.get('artifact_id') or take.get('gpu', {}).get('submitted_at'):
            raise ProjectError('A submitted take is immutable; revise the shot for a changed retry', 409)
        required = next((i for i in bundle['required_inputs'] if i['name'] == name), None)
        if not required or required['kind'] not in REVIEWED_KINDS:
            raise ProjectError('Bind only a required composed first frame or room reference')
        source = Path(filename).resolve()
        with Image.open(source) as image:
            if image.format != 'PNG' or image.size != (1280, 704):
                raise ProjectError('Render input must be a 1280 by 704 PNG')
            image.verify()
        content_hash = media.file_hash(source)
        old = take.get('input_bindings', {}).get(name)
        if old and old['sha256'] == content_hash:
            service._artifact(project, old['artifact_id'])
        else:
            folder = service.store.directory(project_id) / 'takes' / take_id / 'inputs'
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / (uuid.uuid4().hex + '.png')
            with target.open('xb') as output, source.open('rb') as original:
                shutil.copyfileobj(original, output); output.flush(); os.fsync(output.fileno())
            if media.file_hash(target) != content_hash:
                raise ProjectError('Source image changed during import')
            aid = service._register_files(project, [target])[str(target.resolve())]
            take.setdefault('input_bindings', {})[name] = {'artifact_id': aid, 'sha256': content_hash,
                                                         'kind': required['kind']}
            take.pop('input_approval', None)
            project['revision'] += 1
            service.store.save(db, project)
    return service.get(project_id)


def execution_inputs(service, project, take, bundle, require_approval=True):
    manual = [i for i in bundle['required_inputs'] if i['kind'] in REVIEWED_KINDS]
    if manual and require_approval and take.get('input_approval', {}).get('key') != approval_key(take):
        raise ProjectError('The composed first frame or room reference needs human approval', 409)
    resolved = []
    for item in bundle['required_inputs']:
        if item['kind'] in REVIEWED_KINDS:
            binding = take.get('input_bindings', {}).get(item['name'])
            if not binding:
                raise ProjectError('Required image has not been bound: ' + item['name'], 409)
            path, record = service._artifact(project, binding['artifact_id'])
            expected = binding['sha256']
            if record['sha256'] != expected:
                raise ProjectError('Bound image hash differs from its artifact', 409)
        else:
            path = Path(item.get('source') or '').resolve()
            expected = item.get('sha256')
        if not expected or not path.is_file() or media.file_hash(path) != expected:
            raise ProjectError('Required input is missing or changed: ' + item['name'], 409)
        resolved.append({'name': item['name'], 'source': str(path), 'sha256': expected})
    for frame in bundle.get('approved_dependency_frames', {}).values():
        if not frame:
            raise ProjectError('A dependent shot needs its approved parent end frame', 409)
        service._artifact(project, frame['artifact_id'])
    return resolved
