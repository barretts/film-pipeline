import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import minimax_speech as speech


class SpeechWorkflowTests(unittest.TestCase):
    def test_recording_drives_both_conditioning_and_saved_audio(self):
        graph = speech.make_graph('face.png', 'line.wav', 'A woman speaks.', 'take', start=1.25)
        self.assertEqual(graph['19']['inputs']['audio'], ['18', 0])
        self.assertEqual(graph['19']['inputs']['positive'], ['6', 0])
        self.assertEqual(graph['13']['inputs']['latent_image'], ['19', 0])
        self.assertEqual(graph['10']['inputs']['conditioning'], ['19', 3])
        self.assertEqual(graph['16']['inputs']['audio'], ['19', 1])
        self.assertEqual(graph['19']['inputs']['start_seconds'], 1.25)
        self.assertEqual(graph['19']['inputs']['when_short'], 'silence')
        self.assertIn('speaks the supplied voice recording', graph['6']['inputs']['prompt'])

    def test_invalid_frame_counts_and_names_are_rejected(self):
        with self.assertRaises(ValueError):
            speech.make_graph('face.png', 'line.wav', 'Speak', 'take', frames=125)
        with self.assertRaises(ValueError):
            speech.make_graph('face.png', 'line.wav', 'Speak', '../outside')

    def test_short_audio_is_rejected_before_staging_or_submission(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as temporary:
            base = Path(temporary)
            image, audio = base / 'face.png', base / 'voice.wav'
            image.write_bytes(b'image'); audio.write_bytes(b'audio')
            with patch.object(speech, 'BASE', base / 'comfy'), patch.object(speech, 'audio_duration', return_value=3), patch.object(speech.minimax_comfy, 'api') as api:
                with self.assertRaisesRegex(ValueError, 'Recording ends'):
                    speech.main(['submit', '--name', 'short', '--image', str(image), '--audio', str(audio), '--prompt', 'Speak'])
                api.assert_not_called()
                self.assertFalse((base / 'comfy' / 'speech-jobs' / 'short.json').exists())

    def test_ambiguous_submission_persists_and_blocks_duplicate(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as temporary:
            base = Path(temporary)
            image, audio = base / 'face.png', base / 'voice.wav'
            image.write_bytes(b'image'); audio.write_bytes(b'audio')
            arguments = ['submit', '--name', 'take', '--image', str(image), '--audio', str(audio), '--prompt', 'Speak']
            with patch.object(speech, 'BASE', base / 'comfy'), patch.object(speech, 'audio_duration', return_value=10), patch.object(speech.minimax_comfy, 'api', side_effect=TimeoutError('uncertain')) as api:
                with self.assertRaises(TimeoutError):
                    speech.main(arguments)
                state = json.loads((base / 'comfy' / 'speech-jobs' / 'take.json').read_text())
                self.assertEqual(state['phase'], 'submitting')
                with self.assertRaises(FileExistsError):
                    speech.main(arguments)
                self.assertEqual(api.call_count, 1)

    def test_status_distinguishes_running_from_unknown(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'jobs') as temporary:
            base = Path(temporary)
            state = base / 'speech-jobs' / 'take.json'
            state.parent.mkdir()
            state.write_text(json.dumps({'phase': 'submitted', 'prompt_id': 'id-1'}))
            responses = [{}, {'queue_running': [[0, 'id-1']], 'queue_pending': []}]
            with patch.object(speech, 'BASE', base), patch.object(speech.minimax_comfy, 'api', side_effect=responses), patch('builtins.print') as output:
                self.assertEqual(speech.main(['status', '--name', 'take']), 0)
                self.assertEqual(json.loads(output.call_args.args[0])['status'], 'running')


if __name__ == '__main__':
    unittest.main()
