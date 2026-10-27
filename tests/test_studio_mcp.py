import json
import io
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import studio_mcp


class StudioEvidenceTests(unittest.TestCase):
    def test_unicode_result_with_limited_console_encoding(self):
        output = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        client = mock.Mock()
        client.rpc.return_value = {"tools": [{"name": "你好"}]}
        with mock.patch.object(sys, "stdout", output), mock.patch.object(sys, "argv", ["studio_mcp.py", "list"]), \
             mock.patch.object(studio_mcp, "key_from_environment", return_value="key"), \
             mock.patch.object(studio_mcp, "Studio", return_value=client):
            self.assertEqual(studio_mcp.main(), 0)
            output.flush()
            self.assertIn(b"\\u4f60\\u597d", output.buffer.getvalue())

    def test_sse_selects_rpc_response_after_progress(self):
        payload = (b'event: message\r\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\r\n\r\n'
                   b'event: message\r\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\r\n\r\n')
        self.assertTrue(studio_mcp.parse_response(payload, "text/event-stream")["result"]["ok"])
        self.assertEqual(studio_mcp.parse_response(b'{"id":1,"result":{}}', "application/json")["id"], 1)

    def test_redacts_key_nested_credentials_and_inline_media(self):
        obj = {"prompt": "bearer abc123", "hf_token": "different-secret", "nested": {"api_key": "secret"},
               "download_url": "http://127.0.0.1/file?token=signed-secret&X-Amz-Signature=other-secret",
               "media": "data:image/png;base64," + "A" * 500}
        cleaned = json.dumps(studio_mcp.safe(obj, "abc123"))
        self.assertNotIn("abc123", cleaned)
        self.assertNotIn("different-secret", cleaned)
        self.assertNotIn('"secret"', cleaned)
        self.assertNotIn("signed-secret", cleaned)
        self.assertNotIn("other-secret", cleaned)
        self.assertIn("http://127.0.0.1/file?<redacted>", cleaned)
        self.assertNotIn("A" * 500, cleaned)

    def test_success_and_failure_are_recorded_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = studio_mcp.ROOT
            studio_mcp.ROOT = Path(tmp)
            try:
                one = studio_mcp.record_call("studio_status", {}, {"result": "ok"}, 1, 2, "abc123", True)
                two = studio_mcp.record_call("load_model", {"hf_token": "hidden"}, {"error": "abc123"}, 2, 3, "abc123", False)
                lines = (Path(tmp) / "logs" / "mcp_calls.jsonl").read_text(encoding="utf-8").splitlines()
                first, second = map(json.loads, lines)
                self.assertEqual((one, two), (1, 2))
                self.assertTrue(first["ok"])
                self.assertFalse(second["ok"])
                self.assertEqual(second["event"], "fail")
                self.assertEqual(second["duration_s"], 1)
                for file in (Path(tmp) / "logs" / "mcp_raw").glob("*.json"):
                    content = file.read_text(encoding="utf-8")
                    self.assertNotIn("abc123", content)
                    self.assertNotIn("hidden", content)
            finally:
                studio_mcp.ROOT = original

    def test_redacts_url_userinfo_query_and_fragment(self):
        payload = {"message": "See https://name:SECRETVAL@server.invalid/path#access_token=FRAGMENT "
                              "and https://server.invalid/file?X-Amz-Signature=SIGNATURE"}
        result = json.dumps(studio_mcp.safe(payload, "independent-key"))
        for secret in ("name", "SECRETVAL", "FRAGMENT", "SIGNATURE"):
            self.assertNotIn(secret, result)
        self.assertIn("https://server.invalid/path#<redacted>", result)
        self.assertIn("https://server.invalid/file?<redacted>", result)


if __name__ == "__main__":
    unittest.main()
