"""Boundary checks; the real GPU inference is verified separately."""

import io
import hashlib
import ast
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lipsync


class LipSyncBoundaryTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[1] / "tools" / "MuseTalk" / "scripts" / "inference.py").is_file(),
                         "local MuseTalk checkout required")
    def test_video_face_guard_rejects_missing_frames_and_count_mismatch(self):
        # Load only the pure guard, not MuseTalk's CUDA and model imports.
        source = Path(__file__).resolve().parents[1] / "tools" / "MuseTalk" / "scripts" / "inference.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        guard = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == "validate_video_face_tracking")
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[])), str(source), "exec"), namespace)
        validate = namespace["validate_video_face_tracking"]
        validate([(1, 2, 3, 4), (2, 3, 4, 5)], 2)
        with self.assertRaisesRegex(ValueError, "first missing frame: 1"):
            validate([(1, 2, 3, 4), (0, 0, 0, 0)], 2)
        with self.assertRaisesRegex(ValueError, "boxes for 2 video frames"):
            validate([(1, 2, 3, 4)], 2)
        with self.assertRaisesRegex(ValueError, "no decoded frames"):
            validate([], 0)

    def test_successful_engine_exit_without_video_preserves_destination(self):
        with tempfile.TemporaryDirectory(prefix="liptest-") as tmp:
            root = Path(tmp)
            engine = root / "engine"
            weights = engine / "models" / "musetalkV15" / "unet.pth"
            weights.parent.mkdir(parents=True)
            weights.write_bytes(b"weights")
            python = root / "python.exe"
            python.write_bytes(b"interpreter")
            image, audio, output = root / "face.png", root / "voice.wav", root / "result.mp4"
            image.write_bytes(b"image")
            audio.write_bytes(b"audio")
            output.write_bytes(b"existing")
            argv = ["lipsync.py", "--image", str(image), "--audio", str(audio), "--out", str(output), "--overwrite"]
            error = io.StringIO()
            with mock.patch.object(lipsync, "ROOT", root), mock.patch.object(lipsync, "ENGINE", engine), \
                 mock.patch.object(lipsync, "PYTHON", python), mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(sys, "stdout", io.StringIO()), mock.patch.object(sys, "stderr", error), \
                 mock.patch.object(lipsync.shutil, "which", return_value="installed"), \
                 mock.patch.object(lipsync, "probe", return_value={"streams": [{"codec_type": "audio"}], "format": {"duration": "1.0"}}), \
                 mock.patch.object(lipsync, "run"):
                self.assertEqual(lipsync.main(), 1)
            self.assertIn("produced no video", error.getvalue())
            self.assertEqual(output.read_bytes(), b"existing")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
    def test_short_video_does_not_loop_or_overwrite_output(self):
        with tempfile.TemporaryDirectory(prefix="lip-video-") as tmp:
            root = Path(tmp)
            video, audio, output = root / "motion.mp4", root / "voice.wav", root / "result.mp4"
            # The container lasts two seconds because of its audio track, while
            # the actual visual stream lasts only half a second.
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc=size=64x64:rate=25:duration=0.5", "-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=16000:duration=2", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", str(video)], check=True, capture_output=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "sine=frequency=440:sample_rate=16000:duration=1", str(audio)],
                           check=True, capture_output=True)
            before = hashlib.sha256(video.read_bytes()).digest(), hashlib.sha256(audio.read_bytes()).digest()
            output.write_bytes(b"existing")
            result = subprocess.run([sys.executable, str(Path(lipsync.__file__)), "--video", str(video),
                                     "--audio", str(audio), "--out", str(output), "--overwrite"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("shorter than speech", result.stderr)
            self.assertEqual(output.read_bytes(), b"existing")
            self.assertEqual(before, (hashlib.sha256(video.read_bytes()).digest(),
                                      hashlib.sha256(audio.read_bytes()).digest()))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
    def test_source_video_cannot_be_the_output(self):
        with tempfile.TemporaryDirectory(prefix="lip-same-") as tmp:
            root = Path(tmp)
            video, audio = root / "motion.mp4", root / "voice.wav"
            video.write_bytes(b"original")
            audio.write_bytes(b"audio")
            result = subprocess.run([sys.executable, str(Path(lipsync.__file__)), "--video", str(video),
                                     "--audio", str(audio), "--out", str(video), "--overwrite"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("distinct from the inputs", result.stderr)
            self.assertEqual(video.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
