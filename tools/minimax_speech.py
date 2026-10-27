"""Create a local, speech-driven MiniMax H3 shot and safely inspect its job."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

import minimax_comfy

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / 'comfy-local'
FPS = 24


def audio_duration(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                             '-show_entries', 'stream=duration', '-of', 'json', str(path)],
                            check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get('streams', [])
    if not streams or not streams[0].get('duration'):
        raise ValueError('Audio file has no measurable audio stream')
    return float(streams[0]['duration'])


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.speech-state-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf8') as out:
            json.dump(data, out, indent=2, ensure_ascii=True)
            out.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def make_graph(image, audio, prompt, output, frames=124, width=704, height=1280, seed=2801, start=0.0):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', output):
        raise ValueError('Name must contain only letters, numbers, underscores or hyphens')
    if frames < 22 or (frames - 5) % 17 or frames > 362:
        raise ValueError('Frames must be 17k+5, from 22 to 362')
    if width < 32 or height < 32 or width % 32 or height % 32:
        raise ValueError('Width and height must be positive multiples of 32')
    if not math.isfinite(start) or start < 0:
        raise ValueError('Audio start must be a nonnegative finite number')
    if not prompt.strip():
        raise ValueError('Prompt cannot be empty')
    graph = minimax_comfy.speech_graph()
    graph['5']['inputs']['image'] = image
    speech_prompt = (prompt.strip() + ' The character speaks the supplied voice recording naturally '
                     'with precise lip movements, while preserving the character and scene.')
    graph['6']['inputs'].update(prompt=speech_prompt, width=width, height=height, length=frames)
    graph['12']['inputs']['noise_seed'] = seed
    graph['18']['inputs']['audio'] = audio
    graph['19']['inputs']['start_seconds'] = start
    graph['19']['inputs']['when_short'] = 'silence'
    graph['17']['inputs']['filename_prefix'] = f'minimax-speech/{output}'
    return graph


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    submit = subs.add_parser('submit')
    submit.add_argument('--name', required=True, help='Unique take name; never overwrites a previous take')
    submit.add_argument('--image', type=Path, required=True)
    submit.add_argument('--audio', type=Path, required=True)
    submit.add_argument('--prompt', required=True)
    submit.add_argument('--frames', type=int, default=124)
    submit.add_argument('--width', type=int, default=704)
    submit.add_argument('--height', type=int, default=1280)
    submit.add_argument('--seed', type=int, default=2801)
    submit.add_argument('--audio-start', type=float, default=0.0)
    submit.add_argument('--allow-trailing-silence', action='store_true', help='Permit silence only if the requested segment extends past the recording')
    status = subs.add_parser('status')
    status.add_argument('--name', required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', args.name):
        raise ValueError('Name must contain only letters, numbers, underscores or hyphens')
    state_file = BASE / 'speech-jobs' / f'{args.name}.json'
    if args.action == 'status':
        state = json.loads(state_file.read_text(encoding='utf8'))
        if not state.get('prompt_id'):
            raise RuntimeError('Submission outcome is unknown; inspect the ComfyUI queue before retrying')
        job_id = state['prompt_id']
        history = minimax_comfy.api('/history/' + job_id)
        entry = history.get(job_id)
        if entry:
            outcome = entry.get('status', {}).get('status_str', 'unknown')
            report = {'status': outcome, 'outputs': entry.get('outputs', {}),
                      'messages': entry.get('status', {}).get('messages', [])}
        else:
            queue = minimax_comfy.api('/queue')
            status_name = next((label for key, label in (('queue_running', 'running'), ('queue_pending', 'queued'))
                                if any(len(item) > 1 and item[1] == job_id for item in queue.get(key, []))), 'unknown')
            report = {'status': status_name}
        print(json.dumps({'prompt_id': job_id, **report}, ensure_ascii=True))
        return 0
    if state_file.exists():
        raise FileExistsError(f'Job state already exists: {state_file}; inspect it instead of resubmitting')
    image, audio = args.image.resolve(), args.audio.resolve()
    if not image.is_file() or image.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
        raise ValueError('Image must be an existing PNG, JPEG or WebP')
    if not audio.is_file() or audio.suffix.lower() not in ('.wav', '.mp3', '.flac', '.ogg', '.m4a'):
        raise ValueError('Audio must be an existing supported audio file')
    image_name = f'speech-{args.name}{image.suffix.lower()}'
    audio_name = f'speech-{args.name}{audio.suffix.lower()}'
    graph = make_graph(image_name, audio_name, args.prompt, args.name, args.frames, args.width, args.height, args.seed, args.audio_start)
    duration = audio_duration(audio)
    required = args.audio_start + args.frames / FPS
    if duration + .02 < required and not args.allow_trailing_silence:
        raise ValueError(f'Recording ends at {duration:.2f}s, before the requested segment ends at {required:.2f}s; choose fewer frames or explicitly allow trailing silence')
    target = BASE / 'input'
    target.mkdir(parents=True, exist_ok=True)
    for source, name in ((image, image_name), (audio, audio_name)):
        if (target / name).exists():
            raise FileExistsError(f'Input staging file already exists: {target / name}')
    state = {'phase': 'staging', 'image': str(image), 'image_sha256': sha256(image),
             'audio': str(audio), 'audio_sha256': sha256(audio), 'audio_duration_seconds': duration,
             'audio_start_seconds': args.audio_start, 'allow_trailing_silence': args.allow_trailing_silence,
             'frames': args.frames, 'fps': FPS, 'graph': graph}
    atomic_json(state_file, state)
    shutil.copyfile(image, target / image_name)
    shutil.copyfile(audio, target / audio_name)
    state['phase'] = 'submitting'
    atomic_json(state_file, state)
    # If this request is interrupted, leave 'submitting' on disk; never resubmit blindly.
    result = minimax_comfy.api('/prompt', {'prompt': graph, 'client_id': 'film-pipeline-speech'})
    state.update(phase='submitted', prompt_id=result['prompt_id'], response=result)
    atomic_json(state_file, state)
    print(json.dumps({'prompt_id': state['prompt_id'], 'state_file': str(state_file), 'response': result}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'MiniMax speech error: {exc}', file=sys.stderr)
        sys.exit(1)
