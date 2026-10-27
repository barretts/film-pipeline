#!/usr/bin/env python3
"""Call the local Studio MCP server and retain redacted call evidence.

Examples: python tools/studio_mcp.py list
          python tools/studio_mcp.py schema generate_audio
          python tools/studio_mcp.py call studio_status
          python tools/studio_mcp.py call list_models --args '{"source":"local"}'
The bearer key is read from UNSLOTH_API_KEY, never from an argument.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import log_mcp

ENDPOINT = "http://127.0.0.1:8888/mcp/"
ROOT = Path(__file__).resolve().parent.parent


def key_from_environment():
    key = os.environ.get("UNSLOTH_API_KEY", "")
    if not key and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                key = winreg.QueryValueEx(k, "UNSLOTH_API_KEY")[0]
        except OSError:
            pass
    if not key:
        raise RuntimeError("UNSLOTH_API_KEY is unavailable in the process or Windows user environment")
    return key


def parse_response(data, content_type):
    text = data.decode("utf-8")
    if "text/event-stream" in content_type:
        events = []
        for block in text.replace("\r\n", "\n").split("\n\n"):
            payload = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
            if payload:
                events.append(json.loads(payload))
        responses = [event for event in events if "id" in event]
        if not responses:
            raise RuntimeError("MCP stream contained no response")
        return responses[-1]
    return json.loads(text)


class Studio:
    def __init__(self, key, timeout=300):
        self.key = key
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.session = None
        self.rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "film-pipeline", "version": "1"}})

    def rpc(self, method, params):
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = urllib.request.Request(ENDPOINT, data=body, headers=headers)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                self.session = response.headers.get("Mcp-Session-Id") or self.session
                result = parse_response(response.read(), response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            raise RuntimeError("Studio returned HTTP %s" % exc.code) from None
        if "error" in result:
            raise RuntimeError("MCP error: " + str(result["error"].get("message", "unknown error")).replace(self.key, "<redacted>"))
        return result.get("result", {})


def safe(value, key):
    # Replace the actual bearer anywhere, then apply the existing credential and binary redactor.
    serialized = json.dumps(value, ensure_ascii=False).replace(key, "<redacted>")
    expanded = log_mcp.expand(json.loads(serialized))
    def redact_urls(obj):
        if isinstance(obj, dict):
            return {k: redact_urls(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [redact_urls(v) for v in obj]
        if isinstance(obj, str):
            # URLs may carry credentials in userinfo, query strings or fragments.
            def redact_url(match):
                try:
                    parts = urllib.parse.urlsplit(match.group(0))
                    host = parts.netloc.rsplit("@", 1)[-1]
                    return urllib.parse.urlunsplit((parts.scheme, host, parts.path,
                        "<redacted>" if parts.query else "",
                        "<redacted>" if parts.fragment else ""))
                except ValueError:
                    return "<redacted-url>"
            return re.sub(r"(?i)https?://[^\s\"<>\\]+", redact_url, obj)
        return obj
    return log_mcp.clean(redact_urls(expanded), log_mcp.RAW_STR_MAX)


def record_call(name, args, result, started, ended, key, ok):
    args, result = safe(args, key), safe(result, key)
    summary = json.dumps(log_mcp.clean(result, log_mcp.LINE_STR_MAX), ensure_ascii=False)
    record = {"ts_start": log_mcp.iso(started), "ts_end": log_mcp.iso(ended),
              "t_start": round(started, 3), "t_end": round(ended, 3),
              "duration_s": round(ended - started, 3), "ok": ok,
              "event": "post" if ok else "fail", "server": "unsloth-studio",
              "tool": name, "tool_use_id": None, "args": log_mcp.clean(args, log_mcp.LINE_STR_MAX),
              "ids": log_mcp.find_ids(result), "media": log_mcp.find_media(result),
              "result": summary[:log_mcp.RESULT_MAX], "session_id": "direct-local-mcp"}
    raw = {"tool_name": "direct-local-mcp/" + name, "ts_start": record["ts_start"],
           "ts_end": record["ts_end"], "ok": ok, "args": args, "result": result}
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_mcp.locked_append(logs, record, raw)
    return record["seq"]


def main():
    # Model responses can contain text outside the Windows console code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    schema = sub.add_parser("schema")
    schema.add_argument("name")
    call = sub.add_parser("call")
    call.add_argument("name")
    source = call.add_mutually_exclusive_group()
    source.add_argument("--args", default=None, help="JSON object of tool arguments; '-' reads stdin")
    source.add_argument("--args-file", type=Path, help="UTF-8 file containing JSON tool arguments")
    call.add_argument("--timeout", type=float, default=300)
    ns = parser.parse_args()
    key = key_from_environment()
    studio = Studio(key, getattr(ns, "timeout", 300))
    if ns.command in ("list", "schema"):
        items = studio.rpc("tools/list", {}).get("tools", [])
        if ns.command == "list":
            result = [item["name"] for item in items]
        else:
            result = next((item for item in items if item.get("name") == ns.name), None)
            if result is None:
                raise RuntimeError("No such Studio tool")
        print(json.dumps(safe(result, key), ensure_ascii=False, indent=2))
        return 0
    if ns.args_file:
        arg_text = ns.args_file.read_text(encoding="utf-8")
    elif ns.args == "-":
        arg_text = sys.stdin.read()
    else:
        arg_text = ns.args or "{}"
    args = json.loads(arg_text)
    if not isinstance(args, dict):
        raise ValueError("--args must be a JSON object")
    started = time.time()
    try:
        result = studio.rpc("tools/call", {"name": ns.name, "arguments": args})
        ok = not result.get("isError", False)
    except Exception as exc:
        result = {"error": str(exc).replace(key, "<redacted>")}
        ok = False
    seq = record_call(ns.name, args, result, started, time.time(), key, ok)
    print(json.dumps({"seq": seq, "ok": ok, "result": safe(result, key)}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print("Studio error: " + safe(str(exc), os.environ.get("UNSLOTH_API_KEY") or "\0"), file=sys.stderr)
        sys.exit(1)
