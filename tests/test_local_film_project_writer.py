import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from local_film import project_writer as writer
from local_film.project_contract import ProjectError

ROOT = Path(__file__).resolve().parent.parent


class Response(io.BytesIO):
    status = 200


class WriterTests(unittest.TestCase):
    def test_invalid_answer_is_supplied_to_bounded_correction_and_raw_results_survive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'local-runtime/llama').mkdir(parents=True)
            (root / 'local-runtime/models').mkdir()
            (root / 'local-runtime/llama/llama-server.exe').write_bytes(b'not executable: process is mocked')
            (root / 'local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf').write_bytes(b'fixture')
            spec = json.loads((ROOT / 'examples/signalInTheSnow.json').read_text())
            sent = []
            class Opener:
                def open(self, request, timeout):
                    if isinstance(request, str): return Response(b'{}')
                    sent.append(json.loads(request.data))
                    content = 'not-json' if len(sent) == 1 else json.dumps(spec)
                    return Response(json.dumps({'choices': [{'message': {'content': content}}]}).encode())
            process = Mock(); process.poll.return_value = None
            with patch.object(writer, 'ROOT', root), patch.object(writer.subprocess, 'Popen', return_value=process) as spawn, patch.object(writer.urllib.request, 'build_opener', return_value=Opener()):
                result = writer.draft({'spec': spec}, {}, root / 'output', lambda: False)
            self.assertEqual(result['title'], spec['title'])
            self.assertEqual(len(sent), 2)
            self.assertEqual(sent[1]['messages'][-2], {'role': 'assistant', 'content': 'not-json'})
            self.assertIn('Correction:', sent[1]['messages'][-1]['content'])
            self.assertTrue((root / 'output/response-1.json').is_file())
            self.assertTrue((root / 'output/response-2.json').is_file())
            command = spawn.call_args.args[0]
            self.assertEqual(command[command.index('--device') + 1], 'none')
            self.assertEqual(command[command.index('-ngl') + 1], '0')
            self.assertEqual(command[command.index('-c') + 1], '16384')
            process.terminate.assert_called_once(); process.wait.assert_called_once()

    def test_cancel_before_dispatch_never_starts_a_model(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(writer.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(ProjectError, 'cancelled'):
                writer.draft({'spec': {}}, {}, Path(temporary) / 'output', lambda: True)
            spawn.assert_not_called()


if __name__ == '__main__': unittest.main()
