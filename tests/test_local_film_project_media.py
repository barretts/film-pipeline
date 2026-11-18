import json
from pathlib import Path
import tempfile
import time
import unittest
import wave
from unittest.mock import patch

import numpy as np
from local_film import project_media as media
from local_film.project_contract import ProjectError, digest


def write_wave(path, frequency, seconds):
    t = np.arange(round(seconds * 48000)) / 48000
    samples = np.sin(2 * np.pi * frequency * t) * 0.2
    stereo = np.repeat(samples[:, None], 2, axis=1)
    with wave.open(str(path), 'wb') as output:
        output.setparams((2, 2, 48000, len(stereo), 'NONE', 'not compressed'))
        output.writeframes((stereo * 32767).astype('<i2').tobytes())
    return stereo


class ProjectMediaTests(unittest.TestCase):
    def test_persistent_voice_cache_reuses_bytes_and_detects_modified_recordings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); cache = root / 'voice-cache'
            recording = root / 'voice.wav'; write_wave(recording, 500, 0.5)
            voice = {'path': 'local voice', 'sha256': 'voice model'}
            key = digest({'text': 'James.', 'voice': voice})
            media.cache_voice(cache, key, recording, media.file_hash(recording))
            shot = {'id': 'sameLine', 'seconds': 2, 'dialogue': [
                {'character': 'kate', 'source': 'on_screen', 'text': 'James.', 'at_seconds': 0.25}]}
            for name in ('revisionA', 'revisionB'):
                directory = root / name; directory.mkdir()
                with patch.object(media, 'cpu_run') as process:
                    _, lines, _ = media.mix_shot(shot, {'kate': {'voice': voice}}, directory, {}, lambda: False, cache)
                process.assert_not_called()
                self.assertEqual(lines[0]['source_sha256'], media.file_hash(recording))
            recording.write_bytes(b'changed')
            with self.assertRaisesRegex(ProjectError, 'missing or changed'):
                media.load_cached_voice(cache, key)

    def test_cancellation_waits_for_the_real_software_process_to_stop(self):
        original = media.subprocess.Popen
        owned = []
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs); owned.append(child); return child
        start = time.monotonic()
        with patch.object(media.subprocess, 'Popen', side_effect=spawn):
            with self.assertRaisesRegex(ProjectError, 'cancelled'):
                media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-re', '-f', 'lavfi',
                    '-i', 'color=black:s=32x32:r=24:d=20', '-f', 'null', '-'],
                    lambda: time.monotonic() - start > 0.4)
        self.assertEqual(len(owned), 1)
        self.assertIsNotNone(owned[0].poll())
        self.assertLess(time.monotonic() - start, 5)

    def test_radio_voice_is_audible_but_never_in_lipsync_conditioning(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'voice.wav'
            samples = write_wave(source, 700, 0.5)
            voice = {'path': 'already-recorded-voice', 'sha256': 'source'}
            assets = {'kate': {'voice': voice}}
            cache = {digest({'text': 'James.', 'voice': voice}): (samples, source)}
            shot = {'id': 'radio', 'seconds': 2, 'dialogue': [
                {'character': 'kate', 'source': 'radio', 'text': 'James.', 'at_seconds': 0.25}]}
            final, lines, conditioning = media.mix_shot(shot, assets, folder, cache, lambda: False)
            with wave.open(str(conditioning), 'rb') as audio:
                self.assertFalse(any(audio.readframes(audio.getnframes())))
            with wave.open(str(final), 'rb') as audio:
                values = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2')
            self.assertGreater(np.max(np.abs(values)), 1000)
            self.assertEqual(lines[0]['source_sha256'], media.file_hash(source))

    def test_measured_long_line_is_rejected_without_a_truncated_track(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'voice.wav'
            samples = write_wave(source, 700, 2)
            voice = {'path': 'already-recorded-voice'}
            cache = {digest({'text': 'Long line.', 'voice': voice}): (samples, source)}
            shot = {'id': 'tooShort', 'seconds': 1, 'dialogue': [
                {'character': 'kate', 'source': 'on_screen', 'text': 'Long line.', 'at_seconds': 0}]}
            with self.assertRaisesRegex(ProjectError, 'Speech was not truncated'):
                media.mix_shot(shot, {'kate': {'voice': voice}}, folder, cache, lambda: False)
            self.assertFalse((folder / 'tooShort-audio.wav').exists())

    def test_real_assembly_keeps_the_whole_timeline_and_replaces_source_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            shots, paths, preparation, expected_audio = [], {}, {}, []
            for index, (color, frequency) in enumerate([('red', 880), ('blue', 660)]):
                sid = f'shot{index}'
                video = folder / (sid + '.mp4')
                narration = folder / (sid + '.wav')
                expected_audio.append(write_wave(narration, frequency, 2.5))
                media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-y', '-f', 'lavfi',
                    '-i', f'color={color}:s=32x32:r=24:d=2.5', '-f', 'lavfi',
                    '-i', 'sine=frequency=220:sample_rate=48000:duration=2.5',
                    '-c:v', 'libx264', '-threads', '2', '-c:a', 'aac', video])
                shots.append({'id': sid, 'seconds': 2.5})
                paths[sid] = video; preparation[sid] = {'audio': str(narration)}
            project = {'spec': {'shots': shots}, 'preparation': {'shots': preparation}}
            result = media.assemble(project, folder / 'assembly', paths, lambda: False)
            self.assertTrue(result['verification']['full_decode'])
            self.assertAlmostEqual(result['verification']['seconds'], 5, delta=0.12)
            self.assertAlmostEqual(result['verification']['seconds'], 5, delta=1/24000)
            info = media.probe(result['primary'])
            self.assertEqual(next(s for s in info['streams'] if s['codec_type'] == 'video')['nb_frames'], '120')
            pcm = media.cpu_run([media.executable('ffmpeg'), '-v', 'error', '-i', result['primary'],
                                 '-vn', '-f', 's16le', '-ar', '48000', '-ac', '1', '-'])
            values = np.frombuffer(pcm, dtype='<i2').astype(float)
            expected = np.concatenate(expected_audio).mean(axis=1)
            self.assertGreater(float(np.corrcoef(values[:len(expected)], expected)[0, 1]), 0.99,
                               'AAC priming must not shift the prepared soundtrack or shot boundary')
            for start, expected in [(0.5, 880), (3.5, 660)]:
                window = values[round(start*48000):round((start+0.5)*48000)]
                frequencies = np.fft.rfftfreq(len(window), 1/48000)
                peak = frequencies[np.argmax(np.abs(np.fft.rfft(window)))]
                self.assertAlmostEqual(peak, expected, delta=3)
            manifest = json.loads((folder / 'assembly/assembly.json').read_text())
            self.assertEqual(manifest['owner_review'], 'pending')
            self.assertEqual(manifest['source_sha256']['shot0'], media.file_hash(paths['shot0']))


if __name__ == '__main__': unittest.main()
