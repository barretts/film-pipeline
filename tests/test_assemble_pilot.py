"""Integration tests use synthetic media only; they are not generated film assets."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "assemble_pilot.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
class PilotAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="film-test-")
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        # PNG encoder is avoided here: a one-frame BMP is a portable still fixture.
        self.ffmpeg("-f", "lavfi", "-i", "color=red:s=64x48:r=24", "-frames:v", "1", "still.bmp")
        self.ffmpeg("-f", "lavfi", "-i", "color=blue:s=64x48:r=24:d=1", "-c:v", "libx264", "video.mp4")
        self.ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4", "audio.wav")
        self.manifest = self.root / "pilot.json"
        self.output = self.root / "render" / "pilot.mp4"

    def ffmpeg(self, *args):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       cwd=self.root, check=True, capture_output=True)

    def write_manifest(self, shots=None, audio="audio.wav"):
        self.manifest.write_text(json.dumps({"shots": shots or [
            {"file": "still.bmp", "type": "image", "duration": 0.5},
            {"file": "video.mp4", "type": "video", "duration": 0.5},
        ], "audio": audio}), encoding="utf-8")

    def invoke(self, *extra):
        return subprocess.run([sys.executable, str(CLI), str(self.manifest), "--out", str(self.output),
                               "--width", "96", "--height", "64", *extra],
                              capture_output=True, text=True)

    def test_assembles_still_video_and_pads_audio(self):
        self.write_manifest()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                str(self.output)], check=True, capture_output=True, text=True)
        info = json.loads(probe.stdout)
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
        self.assertEqual((video["width"], video["height"], video["r_frame_rate"]), (96, 64, "24/1"))
        self.assertEqual((audio["sample_rate"], audio["channels"]), ("48000", 2))
        self.assertAlmostEqual(float(info["format"]["duration"]), 1.0, delta=0.1)
        self.assertGreater(float(audio["duration"]), 0.9)
        # Check that both sources appear in the intended order, not just stream metadata.
        for timestamp, dominant, other in (("0.2", 0, 2), ("0.7", 2, 0)):
            frame = subprocess.run(["ffmpeg", "-v", "error", "-ss", timestamp, "-i", str(self.output),
                                    "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                   check=True, capture_output=True).stdout
            center = (32 * 96 + 48) * 3
            self.assertGreater(frame[center + dominant], frame[center + other] + 100)

    def test_existing_output_is_not_changed_on_invalid_or_unapproved_run(self):
        self.write_manifest()
        self.output.parent.mkdir()
        self.output.write_bytes(b"original")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b"original")
        self.write_manifest(audio="missing.wav")
        result = self.invoke("--overwrite")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b"original")

    def test_rejects_video_shorter_than_requested(self):
        self.write_manifest([{"file": "video.mp4", "type": "video", "duration": 2}])
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shorter", result.stderr)
        self.assertFalse(self.output.exists())

    def test_unicode_output_with_limited_console_encoding(self):
        self.write_manifest()
        output = self.root / "完成.mp4"
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        result = subprocess.run([sys.executable, str(CLI), str(self.manifest), "--out", str(output),
                                 "--width", "96", "--height", "64"], env=env,
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.is_file())

    @unittest.skipUnless(os.name == "nt" and shutil.which("icacls"), "Windows ACL check")
    def test_output_inherits_destination_directory_permissions(self):
        self.write_manifest()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        acl = subprocess.run(["icacls", str(self.output)], check=True, capture_output=True, text=True).stdout
        self.assertIn("(I)", acl, "output must inherit permissions from its destination directory")


if __name__ == "__main__":
    unittest.main()
