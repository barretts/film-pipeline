"""CPU-only asset preparation, storyboard animatics and reviewed-take assembly."""
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
import uuid
import wave
from pathlib import Path
from .project_contract import ProjectError, digest

ROOT = Path(__file__).resolve().parent.parent


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def cache_voice(cache, key, source, expected_hash):
    """Publish a reference to a complete immutable recording; never overwrite a choice."""
    if cache is None:
        return
    cache = Path(cache).resolve()
    source = Path(source).resolve()
    if not source.is_relative_to(cache.parent) or file_hash(source) != expected_hash:
        raise ProjectError('Cached voice source changed or escaped its project')
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (key + '.json')
    if target.exists():
        return
    temporary = cache / (uuid.uuid4().hex + '.partial')
    temporary.write_text(json.dumps({'key': key, 'source': str(source), 'sha256': expected_hash}), encoding='utf8')
    try:
        os.link(temporary, target)
    except FileExistsError:
        pass
    finally:
        temporary.unlink(missing_ok=True)


def load_cached_voice(cache, key):
    import numpy as np
    if cache is None or not (Path(cache) / (key + '.json')).is_file():
        return None
    cache = Path(cache).resolve()
    entry = json.loads((cache / (key + '.json')).read_text(encoding='utf8'))
    source = Path(entry['source']).resolve()
    if entry['key'] != key or not source.is_relative_to(cache.parent) or not source.is_file() or file_hash(source) != entry['sha256']:
        raise ProjectError('Persistent voice recording is missing or changed; inspect it before preparing again')
    with wave.open(str(source), 'rb') as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (2, 2, 48000) or stream.getnframes() < 1:
            raise ProjectError('Persistent voice recording has an invalid audio format')
        samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float64) / 32768
    return samples, source


def executable(name, runtime=ROOT / 'local-runtime'):
    preferred = runtime / 'piper/piper/piper.exe' if name == 'piper' else runtime / f'ffmpeg/ffmpeg-8.0.1-essentials_build/bin/{name}.exe'
    found = preferred if preferred.is_file() else shutil.which(name)
    if not found:
        raise ProjectError(f'Local {name} executable is missing; see the installation guide')
    return str(found)


def cpu_run(args, cancelled=lambda: False, input_text=None, timeout=180):
    """No shell, no device backends, and cancellation waits for this child to stop."""
    env = os.environ.copy()
    env.update(CUDA_VISIBLE_DEVICES='-1', OMP_NUM_THREADS='4')
    # File redirection avoids pipe deadlocks on verbose FFmpeg/Piper failures.
    import tempfile
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as stdin:
        if input_text is not None:
            stdin.write(input_text.encode('utf-8')); stdin.seek(0)
        if cancelled():
            raise ProjectError('CPU command cancelled', 409)
        process = subprocess.Popen([str(a) for a in args], stdin=stdin, stdout=output, stderr=errors,
                                   env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancelled():
                    raise ProjectError('CPU command cancelled', 409)
                if time.monotonic() - started > timeout:
                    raise ProjectError('CPU subprocess exceeded its time limit')
                time.sleep(0.1)
            output.seek(0); errors.seek(0)
            result, error = output.read(), errors.read()
            if process.returncode:
                raise ProjectError(f'{Path(str(args[0])).name} failed: {error.decode("utf8", errors="replace")[-1500:]}')
            return result
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)


def probe(path, cancelled=lambda: False):
    return json.loads(cpu_run([executable('ffprobe'), '-v', 'error', '-show_streams', '-show_format',
                               '-of', 'json', path], cancelled))


def verify_video(path, expected_seconds, cancelled=lambda: False):
    info = probe(path, cancelled)
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), {})
    audio = next((s for s in info['streams'] if s['codec_type'] == 'audio'), {})
    if (video.get('width'), video.get('height'), video.get('avg_frame_rate')) != (1280, 720, '24/1'):
        raise ProjectError('Video must be 1280×720 at 24 fps')
    if audio.get('sample_rate') != '48000' or audio.get('channels') != 2:
        raise ProjectError('Video needs 48 kHz stereo audio')
    if abs(float(info['format']['duration']) - expected_seconds) > 0.12:
        raise ProjectError('Export duration differs from the approved timeline')
    cpu_run([executable('ffmpeg'), '-v', 'error', '-threads', '2', '-i', path,
             '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'], cancelled)
    return {'full_decode': True, 'seconds': float(info['format']['duration']),
            'width': 1280, 'height': 720, 'fps': 24, 'sample_rate': 48000, 'channels': 2}


def registry_assets(registry, character):
    folder = (Path(registry) / 'characters' / character).resolve()
    definition = folder / 'character.json'
    if not definition.is_file():
        raise ProjectError(f'Unknown character: {character}')
    data = json.loads(definition.read_text(encoding='utf8'))
    result = {'id': character, 'name': data['name'], 'appearance': data['appearance'], 'files': []}
    for relative in dict.fromkeys([data['portrait'], *data['ref_images']]):
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            raise ProjectError(f'Missing or escaping reference for {character}: {relative}')
        result['files'].append({'path': str(path), 'sha256': file_hash(path)})
    voice_name = data['voice_model']
    if Path(voice_name).name != voice_name:
        raise ProjectError('Voice model must be a registry file name')
    voice = ROOT / 'local-runtime/models' / voice_name
    for path in (voice, Path(str(voice) + '.json')):
        if not path.is_file():
            raise ProjectError(f'Voice model/config missing for {character}')
    result['voice'] = {'path': str(voice), 'sha256': file_hash(voice),
                       'config_sha256': file_hash(str(voice) + '.json')}
    return result


def storyboard_card(shot, title, assets, target, index):
    """A labeled planning board, deliberately distinguishable from a generated film frame."""
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    import textwrap
    image = Image.new('RGB', (1280, 720), '#101a29')
    draw = ImageDraw.Draw(image)
    font_path = Path('C:/Windows/Fonts/segoeui.ttf')
    def font(size):
        return ImageFont.truetype(str(font_path), size) if font_path.is_file() else ImageFont.load_default(size=size)
    draw.text((45, 30), f'STORYBOARD · {index + 1:02d} · {shot["seconds"]:g}s', fill='#76c8dc', font=font(23))
    draw.text((45, 75), title, fill='white', font=font(34))
    x = 45
    for member in shot['visible_cast']:
        with Image.open(assets[member]['files'][0]['path']) as portrait:
            thumb = ImageOps.contain(portrait.convert('RGB'), (210, 245))
            image.paste(thumb, (x, 150))
        draw.text((x, 405), assets[member]['name'], fill='#e5b575', font=font(24))
        x += 235
    if not shot['visible_cast']:
        draw.rounded_rectangle((45, 150, 405, 415), radius=12, outline='#76c8dc', width=3)
        draw.text((70, 255), 'INSERT / EMPTY FRAME', fill='#a7bfd1', font=font(22))
    y = 150
    for line in textwrap.wrap(shot['action'], width=49):
        draw.text((560, y), line, fill='white', font=font(25)); y += 36
    for line in textwrap.wrap('Camera: ' + shot['camera'], width=55):
        draw.text((560, y + 15), line, fill='#a7bfd1', font=font(20)); y += 30
    y = 485
    speech = ' / '.join(f'{l["character"]} ({l["source"]}): {l["text"]}' for l in shot['dialogue']) or 'SILENCE — performance and sound effects only'
    for line in textwrap.wrap(speech, width=88):
        draw.text((45, y), line, fill='#e5d49b', font=font(25)); y += 35
    draw.text((45, 660), 'TIMING ANIMATIC · reference portraits / planning cards · not generated footage', fill='#8ca1b4', font=font(20))
    image.save(target)


def mix_shot(shot, assets, directory, voice_cache, cancelled, persistent_cache=None):
    import numpy as np
    count = round(shot['seconds'] * 48000)
    mixed = np.zeros((count, 2), dtype=np.float64)
    conditioning = np.zeros((count, 2), dtype=np.float64)
    lines = []
    for line in shot['dialogue']:
        voice = assets[line['character']]['voice']
        key = digest({'text': line['text'], 'voice': voice})
        if key not in voice_cache:
            cached = load_cached_voice(persistent_cache, key)
            if cached is not None:
                voice_cache[key] = cached
        if key not in voice_cache:
            raw = directory / f'voice-{key[:16]}.wav'
            cpu_run([executable('piper'), '--model', voice['path'], '--output_file', raw],
                    cancelled, line['text'] + '\n')
            normalized = directory / f'voice-{key[:16]}-48k.wav'
            cpu_run([executable('ffmpeg'), '-v', 'error', '-y', '-i', raw,
                     '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', normalized], cancelled)
            with wave.open(str(normalized), 'rb') as stream:
                samples = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').reshape(-1, 2).astype(np.float64) / 32768
            voice_cache[key] = (samples, normalized)
            cache_voice(persistent_cache, key, normalized, file_hash(normalized))
        samples, normalized = voice_cache[key]
        start = round(line['at_seconds'] * 48000)
        if start + len(samples) + 4800 > count:
            raise ProjectError(f'{shot["id"]}: measured speech needs {(start + len(samples) + 4800)/48000:.2f}s; extend the shot or shorten its line. Speech was not truncated.')
        rendered = samples.copy()
        if line['source'] == 'radio':
            # The same source recording is reused at the ending, with radio coloration only here.
            rendered = np.round(rendered * 36) / 36 * 0.7
        mixed[start:start + len(samples)] += rendered
        if line['source'] == 'on_screen':
            conditioning[start:start + len(samples)] += samples
        lines.append({'character': line['character'], 'source': line['source'], 'text': line['text'],
                      'start': line['at_seconds'], 'seconds': len(samples)/48000,
                      'source_audio': str(normalized), 'source_sha256': file_hash(normalized)})
    # Locally synthesized, repeatable atmosphere and two story cues; no downloaded music.
    seed = int(digest(shot['id'])[:8], 16)
    noise = np.random.default_rng(seed).normal(0, 0.007, count)
    mixed += noise[:, None]
    for cue in shot.get('sound_cues', []):
        at = round(float(cue['at_seconds']) * 48000)
        length = min(count-at, 12000)
        if length <= 0:
            continue
        u = np.arange(length) / 48000
        signal = (np.sin(2*np.pi*90*u)*np.exp(-u*32)*0.2 if cue['kind'] == 'knock'
                  else np.random.default_rng(14).normal(0, 0.035, length) * np.exp(-u*10))
        mixed[at:at+length] += signal[:, None]
    target = directory / f'{shot["id"]}-audio.wav'
    with wave.open(str(target), 'wb') as stream:
        stream.setparams((2, 2, 48000, count, 'NONE', 'not compressed'))
        stream.writeframes((np.clip(mixed, -0.98, 0.98) * 32767).astype('<i2').tobytes())
    condition_path = directory / f'{shot["id"]}-conditioning.wav'
    with wave.open(str(condition_path), 'wb') as stream:
        stream.setparams((2, 2, 48000, count, 'NONE', 'not compressed'))
        stream.writeframes((np.clip(conditioning, -0.98, 0.98) * 32767).astype('<i2').tobytes())
    return target, lines, condition_path


def encode_still(image, audio, seconds, target, cancelled):
    cpu_run([executable('ffmpeg'), '-v', 'error', '-y', '-loop', '1', '-framerate', '24',
             '-i', image, '-i', audio, '-t', str(seconds), '-c:v', 'libx264', '-threads', '2',
             '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', '24', '-c:a', 'aac', '-ar', '48000',
             '-ac', '2', '-movflags', '+faststart', target], cancelled)


def concatenate(clips, target, directory, cancelled, durations=None):
    # Generated paths contain no quotes; each input is independently normalized first.
    listing = directory / (target.stem + '-concat.txt')
    listing.write_text(''.join("file '" + str(p.resolve()).replace('\\', '/') .replace("'", "'\\''") + "'\n" for p in clips), encoding='utf8')
    # Decode each MP4 separately: the concat demuxer carries AAC priming into
    # the cut, adding 1024 samples and duplicating a video frame at the start.
    # Reset/trim every stream before concatenating its actual timeline content.
    durations = durations or [float(probe(p, cancelled)['format']['duration']) for p in clips]
    if not clips or len(durations) != len(clips):
        raise ProjectError('Concatenation needs a duration for each clip')
    command = [executable('ffmpeg'), '-v', 'error', '-y']
    filters, labels = [], []
    for index, (clip, seconds) in enumerate(zip(clips, durations)):
        command += ['-threads', '1', '-i', clip]
        filters += [f'[{index}:v:0]trim=duration={seconds:.9f},setpts=PTS-STARTPTS[v{index}]',
                    f'[{index}:a:0]atrim=duration={seconds:.9f},asetpts=PTS-STARTPTS[a{index}]']
        labels.append(f'[v{index}][a{index}]')
    filters.append(''.join(labels) + f'concat=n={len(clips)}:v=1:a=1[v][a]')
    cpu_run(command + ['-filter_complex_threads', '1', '-filter_complex', ';'.join(filters),
             '-map', '[v]', '-map', '[a]', '-t', str(sum(durations)),
             '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
             '-r', '24', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', target], cancelled)


def prepare(project, directory, registry, cancelled, voice_cache_dir=None):
    directory.mkdir(parents=True, exist_ok=False)
    spec = project['spec']
    assets = {c: registry_assets(registry, c) for c in spec['characters']}
    previous = project.get('preparation') or {}
    for old_shot in previous.get('shots', {}).values():
        for line in old_shot.get('lines', []):
            voice = previous['characters'][line['character']]['voice']
            key = digest({'text': line['text'], 'voice': voice})
            cache_voice(voice_cache_dir, key, line['source_audio'], line['source_sha256'])
    result = {'spec_hash': digest(spec), 'characters': assets, 'shots': {}}
    files, clips, cache = [], [], {}
    for index, shot in enumerate(spec['shots']):
        if cancelled():
            raise ProjectError('CPU command cancelled', 409)
        card = directory / f'{shot["id"]}-board.png'
        storyboard_card(shot, spec['title'], assets, card, index)
        audio, lines, conditioning = mix_shot(shot, assets, directory, cache, cancelled, voice_cache_dir)
        clip = directory / f'{shot["id"]}-animatic.mp4'
        encode_still(card, audio, shot['seconds'], clip, cancelled)
        result['shots'][shot['id']] = {'card': str(card), 'audio': str(audio), 'audio_hash': file_hash(audio),
                                           'conditioning_audio': str(conditioning), 'conditioning_hash': file_hash(conditioning),
                                           'lines': lines, 'seconds': shot['seconds']}
        files.extend([card, audio, conditioning, clip]); clips.append(clip)
    movie = directory / 'animatic.mp4'
    concatenate(clips, movie, directory, cancelled, [s['seconds'] for s in spec['shots']])
    result['animatic_check'] = verify_video(movie, sum(s['seconds'] for s in spec['shots']), cancelled)
    result['animatic'] = str(movie)
    manifest = directory / 'preparation.json'
    manifest.write_text(json.dumps(result, indent=2), encoding='utf8')
    files.extend([movie, manifest])
    return {'preparation': result, 'files': files, 'primary': movie}


def assemble(project, directory, paths, cancelled):
    directory.mkdir(parents=True, exist_ok=False)
    clips = []
    for index, shot in enumerate(project['spec']['shots']):
        source = paths[shot['id']]
        info = probe(source, cancelled)
        if float(info['format']['duration']) + 0.03 < shot['seconds']:
            raise ProjectError(f'{shot["id"]}: approved take is shorter than the shot; refusing to truncate the timeline')
        audio = project['preparation']['shots'][shot['id']]['audio']
        clip = directory / f'part-{index:02d}.mp4'
        cpu_run([executable('ffmpeg'), '-v', 'error', '-y', '-i', source, '-i', audio,
                 '-map', '0:v:0', '-map', '1:a:0', '-t', str(shot['seconds']),
                 '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24',
                 '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                 '-c:a', 'aac', '-ar', '48000', '-ac', '2', clip], cancelled)
        clips.append(clip)
    movie = directory / 'film-review.mp4'
    concatenate(clips, movie, directory, cancelled, [s['seconds'] for s in project['spec']['shots']])
    check = verify_video(movie, sum(s['seconds'] for s in project['spec']['shots']), cancelled)
    manifest = directory / 'assembly.json'
    manifest.write_text(json.dumps({'verification': check, 'takes': {s: str(p) for s, p in paths.items()},
                                    'source_sha256': {s: file_hash(p) for s, p in paths.items()},
                                    'spec_hash': digest(project['spec']), 'owner_review': 'pending'}, indent=2), encoding='utf8')
    return {'files': [movie, manifest], 'primary': movie, 'verification': check}
