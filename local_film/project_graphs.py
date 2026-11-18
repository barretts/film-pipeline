"""Build versioned H3 request bundles without contacting or importing a GPU runtime."""
import copy
import json
import math
from pathlib import Path
from .project_contract import ProjectError

TEMPLATES = Path(__file__).with_name('templates')


def prune(graph, outputs):
    pending, needed = list(outputs), set()
    while pending:
        node = pending.pop()
        if node in needed:
            continue
        if node not in graph:
            raise ProjectError(f'Graph has a dangling input: {node}')
        needed.add(node)
        for value in graph[node].get('inputs', {}).values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[1], int):
                pending.append(str(value[0]))
    return {key: copy.deepcopy(value) for key, value in graph.items() if key in needed}


def request_bundle(project, shot, take):
    speaking = [line for line in shot['dialogue'] if line['source'] == 'on_screen']
    if len({line['character'] for line in speaking}) > 1:
        raise ProjectError('Split a shot with multiple on-screen speakers before preparing H3')
    first_frame = bool(speaking) or shot.get('conditioning_mode') == 'first-frame'
    template = 'h3SpeechV1' if first_frame else 'h3ActionV1'
    graph = json.loads((TEMPLATES / (template + '.json')).read_text(encoding='utf8'))
    frames = 5 + 17 * math.ceil((shot['seconds'] * 24 - 5) / 17)
    if frames > 362:
        raise ProjectError('H3 shot exceeds the single-take frame limit; split it first')
    prefix = f'films/{project["project_id"]}/{take["id"]}'
    audio_name = prefix + '/audio.wav'
    prompt = '\n'.join([project['spec']['style'], shot['prompt'], 'Camera: ' + shot['camera'],
                        'Action: ' + shot['action'], 'Visible cast: ' + (', '.join(shot['visible_cast']) or 'no people'),
                        'No extra people, dialogue, camera moves, or cuts.'])
    prepared_audio = project['preparation']['shots'][shot['id']]
    dependencies = {name: next(t for t in project['takes'] if t['id'] == tid).get('end_frame')
                    for name, tid in take['dependency_takes'].items()}
    required = [{'name': audio_name, 'source': prepared_audio.get('conditioning_audio', prepared_audio['audio']),
                 'kind': 'on-screen-speech-or-silence',
                 'sha256': prepared_audio.get('conditioning_hash', prepared_audio['audio_hash'])}]
    if first_frame:
        graph['5']['inputs']['image'] = prefix + '/first-frame.png'
        instruction = (' Speak the supplied recording naturally with precise lip movements.' if speaking else
                       ' Preserve the supplied first-frame composition and the locked camera. No people or dialogue.' if not shot['visible_cast'] else
                       ' Preserve the supplied first-frame composition and the locked camera. Perform only the stated action.')
        graph['6']['inputs'].update(prompt=prompt + instruction,
                                    width=1280, height=704, length=frames)
        graph['12']['inputs']['noise_seed'] = int(take['input_hash'][:8], 16)
        graph['17']['inputs']['filename_prefix'] = prefix
        graph['18']['inputs']['audio'] = audio_name
        required.append({'name': prefix + '/first-frame.png',
                         'kind': 'composed-first-frame' if shot['visible_cast'] else 'room-reference',
                         'status': 'needs-generation-and-human-review',
                         'references': {c: project['preparation']['characters'][c]['files'] for c in shot['visible_cast']},
                         'before': shot['before']})
        outputs = ['17']
    else:
        settings = graph['157']['inputs']
        for key in list(settings):
            if key.startswith('ref_images.'):
                del settings[key]
        refs = shot['visible_cast'] or ['room']
        for index, character in enumerate(refs):
            node = str(170 + index)
            name = prefix + f'/reference-{index}.png'
            graph[node] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            settings[f'ref_images.ref_image_{index}'] = [node, 0]
            source = (project['preparation']['characters'][character]['files'][0]['path']
                      if character != 'room' else None)
            source_hash = project['preparation']['characters'][character]['files'][0].get('sha256') if source else None
            required.append({'name': name, 'source': source, 'sha256': source_hash,
                             'kind': 'character-reference' if source else 'room-reference',
                             'status': 'available' if source else 'needs-generation-and-human-review'})
        settings.update(prompt=prompt, width=1280, height=704, length=frames)
        for frame in dependencies.values():
            if not frame:
                continue
            index = len([k for k in settings if k.startswith('ref_images.')])
            node, name = str(170 + index), prefix + f'/reference-{index}.png'
            graph[node] = {'class_type': 'LoadImage', 'inputs': {'image': name}}
            settings[f'ref_images.ref_image_{index}'] = [node, 0]
            required.append({'name': name, 'source': frame['path'], 'sha256': frame['sha256'],
                             'kind': 'approved-dependency-frame'})
        graph['130']['inputs']['noise_seed'] = int(take['input_hash'][:8], 16)
        graph['136']['inputs']['filename_prefix'] = prefix
        graph['18']['inputs']['audio'] = audio_name
        outputs = ['136']
    graph = prune(graph, outputs)
    if any(value['class_type'] == 'MiniMaxH3AddGuide' for value in graph.values()):
        raise ProjectError('Character blockout guides are not supported by these templates')
    return {'schema_version': 1, 'template': template, 'project_id': project['project_id'],
            'take_id': take['id'], 'input_hash': take['input_hash'], 'gpu_policy': 'disabled',
            'status': 'awaiting-gpu', 'conditioning_mode': 'first-frame' if first_frame else 'reference',
            'frames': frames, 'fps': 24, 'trim_seconds': shot['seconds'],
            'required_inputs': required, 'graph': graph,
            'approved_dependency_frames': dependencies,
            'note': 'Prepared request only. No submission occurred. First-frame/room generation and real GPU validation are deferred.'}
