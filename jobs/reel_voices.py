"""Generate three local Kokoro narration clips through Studio MCP."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import studio_mcp

MODEL = "audio-cpp/audio.cpp-gguf/Kokoro-82M-GGUF"
SCRIPTS = [
    "Tomorrow, this room will forget me. So I hid this message inside the silence between two heartbeats. If you can hear it, the room missed one.",
    "I taught the machine a word: home. It drew a door. Behind that door was a room. And in that room... another me.",
    "The machine asked what I wanted to remember. I said: a face. It showed me yours. Now tell me... have we met before?",
]


def main():
    key = studio_mcp.key_from_environment()
    api = studio_mcp.Studio(key, timeout=300)

    def call(name, args):
        start = time.time()
        try:
            result = api.rpc("tools/call", {"name": name, "arguments": args})
            ok = not result.get("isError", False)
        except Exception as exc:
            result, ok = {"error": str(exc)}, False
        seq = studio_mcp.record_call(name, args, result, start, time.time(), key, ok)
        if not ok:
            raise RuntimeError(f"{name} failed; inspect redacted MCP sequence {seq}")
        payload = result.get("structuredContent", {})
        print(f"{name}: seq {seq}", flush=True)
        return payload

    result = call("load_model", {"kind": "tts", "model": MODEL, "device": "gpu", "wait_s": 50})
    status = result.get("status")
    job = result.get("job_id")
    if status == "loading" and job:
        for _ in range(12):
            result = call("get_job", {"kind": "load", "id": job, "wait_s": 30})
            if result.get("status") not in ("loading", "running", "pending"):
                break
        else:
            raise RuntimeError(f"Model load still pending; inspect job {job}, do not reload")
        if result.get("status") not in ("completed", "success", "loaded"):
            raise RuntimeError(f"Model load ended with status {result.get('status')}; inspect job {job}")
    elif status in ("failed", "error"):
        raise RuntimeError(f"Model load failed: {status}")

    target = ROOT / "audio" / "reels"
    target.mkdir(parents=True, exist_ok=True)
    try:
        for index, script in enumerate(SCRIPTS, 1):
            path = target / f"{index:02}.wav"
            if path.exists():
                raise RuntimeError(f"Destination exists: {path}")
            result = call("generate_audio", {"workflow": "speak", "text": script,
                "return_media": "link"})
            clips = result.get("clips") or []
            if len(clips) != 1:
                raise RuntimeError(f"Expected one clip; got {len(clips)}")
            clip = clips[0]
            url = clip.get("download_url") or clip.get("url")
            parsed = urllib.parse.urlsplit(url or "")
            if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8888:
                raise RuntimeError("Unexpected clip URL; refusing nonlocal transfer")
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=90) as response:
                contents = response.read()
            if len(contents) < 44 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
                raise RuntimeError("Studio response is not a WAV file")
            fd, staged = tempfile.mkstemp(prefix=".narration-", suffix=".wav", dir=target)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(contents)
                os.replace(staged, path)
            finally:
                if os.path.exists(staged):
                    os.unlink(staged)
            print(f"{path}: duration {clip.get('duration_s')}s, Studio default voice", flush=True)
    finally:
        call("unload_model", {"kind": "tts"})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("error:", str(exc), file=sys.stderr)
        sys.exit(1)
