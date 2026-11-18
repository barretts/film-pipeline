import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import Mock

from steering.openrouter_client import CloudPlanner, LUNA
from steering.openrouter_shot import ensure_job
from steering.reference_link import file_handler


class OpenRouterShotTests(unittest.TestCase):
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
