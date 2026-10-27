"""Boundary and recovery tests; no model or network is used."""

import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import video_motion


class FakeStudio:
    calls = []

    def __init__(self, key, timeout):
        pass

    def rpc(self, method, request):
        name = request["name"]
        self.calls.append(name)
        if name == "studio_status":
            return {"structuredContent": {"video": {"loaded": True, "generating": False},
                                           "image": {"generating": False}}}
        if name == "load_model":
            return {"structuredContent": {"status": "loaded"}}
        if name == "generate_video":
            raise TimeoutError("connection lost before response")
        raise AssertionError(name)


class FakeResumingStudio(FakeStudio):
    calls = []

    def rpc(self, method, request):
        name = request["name"]
        if name == "get_job":
            self.calls.append(name)
            return {"structuredContent": {"status": "completed"}}
        return super().rpc(method, request)


class VideoMotionTests(unittest.TestCase):
    def test_interrupted_load_resumes_saved_job_without_second_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portrait, output = root / "input.png", root / "output.mp4"
            portrait.write_bytes(b"portrait")
            argv = ["video_motion.py", "--image", str(portrait), "--prompt", "move her hand", "--out", str(output)]
            request = {"image": portrait.resolve().as_posix(), "image_sha256": hashlib.sha256(b"portrait").hexdigest(),
                       "prompt": "move her hand", "output": output.resolve().as_posix(), "size": "704x1280",
                       "frames": 73, "fps": 16, "steps": 16, "seed": 2801}
            video_motion.save_state(output.with_suffix(".wan-job.json"),
                                    {"request": request, "phase": "loading", "load_job_id": "existing-load"})
            FakeResumingStudio.calls = []
            with mock.patch.object(sys, "argv", argv), mock.patch.object(sys, "stdout", io.StringIO()), \
                 mock.patch.object(sys, "stderr", io.StringIO()), \
                 mock.patch.object(video_motion.studio_mcp, "key_from_environment", return_value="test-key"), \
                 mock.patch.object(video_motion.studio_mcp, "Studio", FakeResumingStudio), \
                 mock.patch.object(video_motion.studio_mcp, "record_call", return_value=1):
                self.assertEqual(video_motion.main(), 1)
            self.assertEqual(FakeResumingStudio.calls, ["get_job", "studio_status", "generate_video"])

    def test_local_url_rejects_nonlocal_or_wrong_port(self):
        self.assertTrue(video_motion.local_url("http://127.0.0.1:8888/media/file?sig=abc"))
        for url in ("https://127.0.0.1:8888/media", "http://127.0.0.1:8000/media",
                    "http://example.org:8888/media", "http://127.0.0.1.evil:8888/media"):
            self.assertFalse(video_motion.local_url(url))

    def test_ambiguous_submission_is_not_repeated_on_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            portrait, output = root / "input.png", root / "output.mp4"
            portrait.write_bytes(b"portrait")
            argv = ["video_motion.py", "--image", str(portrait), "--prompt", "move her hand",
                    "--out", str(output)]
            FakeStudio.calls = []
            err = io.StringIO()
            with mock.patch.object(sys, "argv", argv), mock.patch.object(sys, "stdout", io.StringIO()), \
                 mock.patch.object(sys, "stderr", err), \
                 mock.patch.object(video_motion.studio_mcp, "key_from_environment", return_value="test-key"), \
                 mock.patch.object(video_motion.studio_mcp, "Studio", FakeStudio), \
                 mock.patch.object(video_motion.studio_mcp, "record_call", return_value=1):
                self.assertEqual(video_motion.main(), 1)
                state = json.loads(output.with_suffix(".wan-job.json").read_text(encoding="utf-8"))
                self.assertEqual(state["phase"], "unknown_submit")
                first_calls = list(FakeStudio.calls)
                self.assertEqual(video_motion.main(), 1)
                self.assertEqual(FakeStudio.calls, first_calls)
            self.assertEqual(first_calls.count("generate_video"), 1)
            self.assertFalse(output.exists())
            self.assertIn("outcome is unknown", err.getvalue())


if __name__ == "__main__":
    unittest.main()
