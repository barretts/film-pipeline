"""Version-one contracts for reviewed short films; no model or service imports."""
import copy
import hashlib
import json
import math
import re


class ProjectError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identifier(value, label='id'):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', value):
        raise ProjectError(f'Invalid {label}')
    return value


def text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ProjectError(f'{label} must be nonempty text')
    return value.strip()


def seconds(value, label, minimum=0, maximum=15):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ProjectError(f'{label} must be between {minimum} and {maximum}')
    return float(value)


def validate_spec(value):
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ProjectError('Film specification needs schema_version: 1')
    spec = copy.deepcopy(value)
    for key in ('title', 'brief', 'style'):
        spec[key] = text(spec.get(key), key)
    cast = spec.get('characters')
    if not isinstance(cast, list) or not 1 <= len(cast) <= 6 or len(set(cast)) != len(cast):
        raise ProjectError('characters must contain 1–6 unique registry ids')
    for member in cast:
        identifier(member, 'character')
    output = {'width': 1280, 'height': 720, 'fps': 24, 'sample_rate': 48000, 'channels': 2}
    if 'output' in spec and spec['output'] != output:
        raise ProjectError('Version 1 exports 1280×720, 24 fps, 48 kHz stereo')
    spec['output'] = output
    shots = spec.get('shots')
    if not isinstance(shots, list) or not 1 <= len(shots) <= 12:
        raise ProjectError('A film needs 1–12 shots')
    seen = set()
    state = copy.deepcopy(spec.get('initial_state', {}))
    if not isinstance(state, dict):
        raise ProjectError('initial_state must be an object')
    if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in state.items()):
        raise ProjectError('initial_state needs text keys and values')
    for shot in shots:
        if not isinstance(shot, dict):
            raise ProjectError('Each shot must be an object')
        sid = identifier(shot.get('id'), 'shot id')
        if sid in seen:
            raise ProjectError('Shot ids must be unique')
        for key in ('action', 'prompt', 'camera'):
            shot[key] = text(shot.get(key), f'{sid}.{key}')
        shot['seconds'] = seconds(shot.get('seconds'), f'{sid}.seconds', 1)
        visible = shot.get('visible_cast')
        offscreen = shot.get('offscreen_cast', [])
        if any(not isinstance(items, list) or len(items) != len(set(items)) or not set(items) <= set(cast)
               for items in (visible, offscreen)):
            raise ProjectError(f'{sid}: cast lists must contain unique registered characters')
        if set(visible) & set(offscreen):
            raise ProjectError(f'{sid}: visible and offscreen cast overlap')
        shot['offscreen_cast'] = offscreen
        requires = shot.get('requires', [])
        if not isinstance(requires, list) or len(set(requires)) != len(requires) or not set(requires) <= seen:
            raise ProjectError(f'{sid}: dependencies must refer to earlier shots')
        shot['requires'] = requires
        for key in ('before', 'after'):
            if not isinstance(shot.get(key), dict) or not shot[key]:
                raise ProjectError(f'{sid}: explicit {key} state required')
            if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() for k, v in shot[key].items()):
                raise ProjectError(f'{sid}: states need text keys and values')
        for key, prior in shot['before'].items():
            if key in state and state[key] != prior:
                raise ProjectError(f'{sid}: before.{key} contradicts preceding state')
        reentry = shot.get('re_entry_cast', [])
        if not isinstance(reentry, list) or not set(reentry) <= set(cast):
            raise ProjectError(f'{sid}: re_entry_cast must name registered characters')
        for character in cast:
            if state.get(character) == 'gone' and (character in visible or shot['after'].get(character, 'gone') != 'gone') and character not in reentry:
                raise ProjectError(f'{sid}: {character} needs explicit re_entry_cast after being gone')
        state.update(shot['after'])
        lines = shot.get('dialogue')
        if not isinstance(lines, list) or type(shot.get('silence')) is not bool or shot['silence'] != (not lines):
            raise ProjectError(f'{sid}: dialogue list and explicit silence must agree')
        for line in lines:
            if not isinstance(line, dict) or line.get('character') not in cast:
                raise ProjectError(f'{sid}: dialogue character is outside the film cast')
            line['text'] = text(line.get('text'), f'{sid}.dialogue.text')
            if line.get('source') not in ('on_screen', 'off_screen', 'radio'):
                raise ProjectError(f'{sid}: dialogue needs on_screen, off_screen or radio source')
            if line['source'] == 'on_screen' and line['character'] not in visible:
                raise ProjectError(f'{sid}: on-screen speaker must be visible')
            if line['character'] not in visible + offscreen:
                raise ProjectError(f'{sid}: audible character must be declared in cast lists')
            line['at_seconds'] = seconds(line.get('at_seconds', 0.3), f'{sid}.dialogue.at_seconds', maximum=shot['seconds'])
        if len({line['character'] for line in lines if line['source'] == 'on_screen'}) > 1:
            raise ProjectError(f'{sid}: split multiple on-screen speakers into separate shots')
        mode = shot.get('conditioning_mode', 'auto')
        if mode not in ('auto', 'first-frame', 'reference'):
            raise ProjectError(f'{sid}: conditioning_mode must be auto, first-frame or reference')
        if mode == 'reference' and any(line['source'] == 'on_screen' for line in lines):
            raise ProjectError(f'{sid}: on-screen speech requires first-frame conditioning')
        cues = shot.get('sound_cues', [])
        if not isinstance(cues, list):
            raise ProjectError(f'{sid}: sound_cues must be a list')
        for cue in cues:
            if not isinstance(cue, dict) or cue.get('kind') not in ('knock', 'static'):
                raise ProjectError(f'{sid}: supported sound cues are knock and static')
            seconds(cue.get('at_seconds'), f'{sid}.sound_cue.at_seconds', maximum=shot['seconds'])
        seen.add(sid)
    total = sum(s['seconds'] for s in shots)
    if not 5 <= total <= 180:
        raise ProjectError('Film duration must be 5–180 seconds')
    return spec


GPU_ACTIVE = {'preparing', 'submitting', 'submission-unknown', 'queued', 'running',
              'cancel-pending', 'output-pending', 'recovery-blocked'}


def gpu_active(take):
    return take.get('gpu', {}).get('state') in GPU_ACTIVE


def attempted_take(take):
    return bool(take.get('artifact_id') or take.get('gpu', {}).get('submitted_at'))


def approved_takes(project):
    """Resolve only approvals whose inputs and approved dependencies still match."""
    approved = {}
    preparation = project.get('preparation') or {}
    for shot in project['spec']['shots']:
        if any(dep not in approved for dep in shot['requires']):
            continue
        key = take_key(project, shot, approved)
        for take in reversed(project.get('takes', [])):
            reviews = [r for r in project.get('reviews', []) if r['take_id'] == take['id']]
            if (take['shot_id'] == shot['id'] and take['input_hash'] == key and
                    take.get('artifact_id') and reviews and reviews[-1]['decision'] == 'approve' and preparation):
                approved[shot['id']] = take
                break
    return approved


def take_key(project, shot, approved):
    preparation = project.get('preparation') or {}
    cast = set(shot['visible_cast'] + shot['offscreen_cast'])
    return digest({'shot': shot, 'style': project['spec']['style'],
                   'assets': {c: preparation.get('characters', {}).get(c) for c in sorted(cast)},
                   'audio': preparation.get('shots', {}).get(shot['id'], {}).get('audio_hash'),
                   'dependencies': {d: approved[d]['id'] for d in shot['requires'] if d in approved},
                   'template_version': 1})
