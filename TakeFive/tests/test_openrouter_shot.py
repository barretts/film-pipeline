import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import Mock, patch
import urllib.error
import numpy as np

from steering.openrouter_client import CloudPlanner, LUNA
from steering.openrouter_shot import edit_to_timeline, ensure_job
from steering.reference_link import file_handler, verify_url
from takefive.production import ffmpeg, probe
from takefive.script import binary


class OpenRouterShotTests(unittest.TestCase):
    def test_provider_overrun_cuts_picture_and_sound_on_the_editor_frame(self):
        with TemporaryDirectory() as work:
            original, edit = (Path(work)/n for n in ("original.mp4", "edit.mp4"))
            ffmpeg("-f", "lavfi", "-i", "testsrc2=size=96x64:rate=24:duration=1.167",
                   "-f", "lavfi", "-i", "sine=frequency=400:duration=0.86,adelay=500:all=1", "-vf", "setpts=PTS+2",
                   "-fps_mode:v", "passthrough", "-c:v", "libx264", "-c:a", "aac", original)
            result = edit_to_timeline(original, edit, 1, probe(original))
            self.assertEqual(result["frames"], 24)
            self.assertAlmostEqual(result["source_video_start_seconds"], 2/24, delta=0.001)
            for stream in probe(edit)["streams"]:
                self.assertAlmostEqual(float(stream["start_time"]), 0, places=4)
                self.assertAlmostEqual(float(stream["duration"]), 1, places=3)
            samples = subprocess.check_output([binary("ffmpeg"), "-v", "error", "-i", str(edit), "-map", "0:a:0",
                                               "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"])
            onset = np.flatnonzero(np.abs(np.frombuffer(samples, dtype="<i2").astype(int)) > 500)[0] / 16000
            self.assertAlmostEqual(onset, 0.5-result["source_video_start_seconds"], delta=0.01)

    def test_quick_link_dns_recovery_still_checks_exact_video_bytes(self):
        stale = urllib.error.URLError(socket.gaierror(11001, "unknown host"))
        url = "https://example.trycloudflare.com/one/guide.mp4"
        with TemporaryDirectory() as work:
            guide = Path(work)/"guide.mp4"
            guide.write_bytes(b"the guide")
            with patch("steering.reference_link.urllib.request.urlopen", side_effect=stale), \
                    patch("steering.reference_link.read_tunnel_via_cloudflare", return_value=guide.read_bytes()) as fetch:
                verify_url(url, guide, quick_tunnel=True)
                self.assertEqual(fetch.call_args.args[0].hostname, "example.trycloudflare.com")
                fetch.return_value = b"wrong"
                with self.assertRaisesRegex(ValueError, "exact|exported guide"):
                    verify_url(url, guide, quick_tunnel=True)
                with self.assertRaises(urllib.error.URLError):
                    verify_url("https://example.org/guide.mp4", guide, quick_tunnel=True)

    def test_accepted_or_interrupted_submission_is_never_posted_twice(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted), TemporaryDirectory() as work:
                folder = Path(work)
                router = Mock()
                router.json.return_value = {"id":"job-one","status":"pending","urls":["temporary-secret-link"]}
                url = "https://example.org/private-reference"
                if interrupted:
                    router.json.side_effect = TimeoutError()
                    with self.assertRaises(TimeoutError):
                        ensure_job(router, folder, {}, url, {})
                    with self.assertRaises(RuntimeError):
                        ensure_job(router, folder, {}, url, {})
                else:
                    result = ensure_job(router, folder, {}, url, {})
                    self.assertEqual(result, ensure_job(router, folder, {}, url, {}))
                    self.assertEqual(result, {"job":{"id":"job-one","status":"pending"}})
                    self.assertNotIn(url, (folder/"receipt.json").read_text())
                router.json.assert_called_once_with("/videos", {"input_references":[{"type":"video_url","video_url":{"url":url}}]})

    def test_temporary_origin_serves_only_one_file_and_accepts_range_reads(self):
        data = b"sample video bytes"
        with ThreadingHTTPServer(("127.0.0.1", 0), file_handler("/token/guide.mp4", data)) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                client = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                client.request("GET", "/token/guide.mp4", headers={"Range":"bytes=2-6"})
                with client.getresponse() as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), data[2:7])
                client.request("GET", "/")
                with client.getresponse() as response:
                    self.assertEqual(response.status, 404)
                client.close()
            finally:
                server.shutdown()
                worker.join()

    def test_planner_reuses_checked_answer_and_actual_charge(self):
        router = Mock()
        router.json.return_value = {"id":"gen-1","model":LUNA,"usage":{"cost":0.001},
                                    "choices":[{"finish_reason":"stop","message":{"content":json.dumps("wide")}}]}
        with TemporaryDirectory() as work:
            args = ("direct","story",{"type":"string","enum":["wide","close"]},19,Path(work),400,lambda value: None)
            for _ in range(2):
                planner = CloudPlanner(router,LUNA)
                self.assertEqual(planner.ask(*args),"wide")
                self.assertEqual(planner.receipts[0]["usage"]["cost"],0.001)
        self.assertEqual(router.json.call_count,1)
