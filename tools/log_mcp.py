#!/usr/bin/env python3
"""Claude Code hook: log every Unsloth Studio MCP call.

Wired up by .claude/settings.json (see templates/claude-settings.json):
    py -3 tools/log_mcp.py pre    (PreToolUse)
    py -3 tools/log_mcp.py post   (PostToolUse)
    py -3 tools/log_mcp.py fail   (PostToolUseFailure)

Reads the hook event JSON from stdin and writes:
    logs/mcp_calls.jsonl       one compact line per call (the "truth log")
    logs/mcp_raw/<seq>_<tool>.json   full cleaned args + response for that call

Rules: standard library only, never blocks a tool call (always exits 0),
never stores secrets (keys named like auth/token/key are redacted, sk-unsloth-* masked),
drops inline binary/base64 media so the log stays small.
"""
import hashlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

SERVER_PREFIX = "mcp__unsloth"     # matches mcp__unsloth__* and mcp__unsloth-studio__*
LINE_STR_MAX = 400                 # per-string cap inside the compact JSONL line
RAW_STR_MAX = 200_000              # per-string cap inside the raw file
RESULT_MAX = 2000                  # chars of result summary kept in the JSONL line
# Redact values whose KEY looks like a credential. Whole-key match (plus *_token / *_secret / *_api_key
# suffixes) so that ordinary fields such as max_tokens, num_tokens or tokenizer are kept.
SECRET_KEY_RE = re.compile(
    r"^(authorization|proxy-authorization|cookie|set-cookie|password|passwd|secret|token|bearer|"
    r"api[_-]?key|x[_-]api[_-]key|access[_-]?token|refresh[_-]?token|auth[_-]?token|id[_-]?token|"
    r"session[_-]?token|hf[_-]?token|client[_-]?secret|private[_-]?key)$"
    r"|[_-](secret|password|api[_-]?key|token)$",
    re.I,
)
SK_RE = re.compile(r"sk-unsloth-[A-Za-z0-9_\-]+")
B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]{200,}$")
MEDIA_RE = re.compile(
    r"[^\s\"'<>()]+\.(?:png|jpe?g|webp|gif|mp4|webm|mov|mkv|wav|flac|mp3|ogg|m4a|gguf|safetensors|csv|srt|vtt)\b",
    re.I,
)
ID_KEYS = {"job_id", "queue_id", "run_id", "training_id", "export_id", "task_id", "media_id", "id"}


def iso(t):
    if t is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t)) + ".%03d" % int((t % 1) * 1000)


def expand(obj, depth=0):
    """Parse JSON that arrives as text (MCP content blocks usually carry JSON strings)."""
    if depth > 8:
        return obj
    if isinstance(obj, str):
        s = obj.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return expand(json.loads(s), depth + 1)
            except Exception:
                return obj
        return obj
    if isinstance(obj, dict):
        return {k: expand(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand(v, depth + 1) for v in obj]
    return obj


def clean(obj, max_str, depth=0):
    """JSON-safe copy: secrets redacted, binary dropped, long strings truncated."""
    if depth > 10:
        return "<depth-limit>"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[str(k)] = "<redacted>" if SECRET_KEY_RE.search(str(k)) else clean(v, max_str, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        items = [clean(v, max_str, depth + 1) for v in list(obj)[:200]]
        if len(obj) > 200:
            items.append("<+%d more items>" % (len(obj) - 200))
        return items
    if isinstance(obj, str):
        if obj.startswith("data:") or (len(obj) >= 200 and B64_RE.match(obj)):
            return "<binary %d chars dropped>" % len(obj)
        s = SK_RE.sub("sk-unsloth-<redacted>", obj)
        if len(s) > max_str:
            return s[:max_str] + "...<+%d chars>" % (len(s) - max_str)
        return s
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    return str(obj)


def walk(obj):
    """Yield (key, value) pairs for every dict entry and (None, str) for every string."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                yield k, v
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, str):
            yield None, cur


def find_ids(obj):
    found = []
    for k, v in walk(obj):
        if k is not None and str(k).lower() in ID_KEYS and isinstance(v, (str, int)) and str(v):
            item = "%s=%s" % (k, v)
            if item not in found:
                found.append(item)
        if len(found) >= 12:
            break
    return found


def find_media(obj):
    found = []
    for k, v in walk(obj):
        if isinstance(v, str) and not v.startswith("data:"):
            for m in MEDIA_RE.finditer(v):
                s = m.group(0)
                if s not in found:
                    found.append(s)
        if len(found) >= 20:
            break
    return found


def looks_like_error(obj):
    if isinstance(obj, dict):
        if obj.get("isError") is True or obj.get("is_error") is True:
            return True
        if obj.get("error"):
            return True
    return False


def locked_append(logs, record, raw_payload):
    lock = logs / ".lock"
    seq_file = logs / ".seq"
    fd = None
    deadline = time.time() + 5
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 10:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.time() > deadline:
                break  # give up on the lock rather than block the agent
            time.sleep(0.05)
    try:
        seq = 0
        try:
            seq = int((seq_file.read_text(encoding="utf-8").strip() or "0"))
        except Exception:
            seq = 0
        seq += 1
        seq_file.write_text(str(seq), encoding="utf-8")
        record["seq"] = seq
        raw_dir = logs / "mcp_raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_name = "%06d_%s.json" % (seq, re.sub(r"[^A-Za-z0-9_.-]", "_", record["tool"])[:40])
        record["raw"] = "logs/mcp_raw/" + raw_name
        raw_payload["seq"] = seq
        (raw_dir / raw_name).write_text(json.dumps(raw_payload, ensure_ascii=False, indent=1), encoding="utf-8")
        with open(logs / "mcp_calls.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        if fd is not None:
            os.close(fd)
            try:
                lock.unlink()
            except FileNotFoundError:
                pass


def split_server_tool(tool_name):
    """Split a fully-qualified MCP tool name into (server, short_tool).

    OMP CLI sanitizes server+tool to underscores and joins them with a single '_', so
    a call to Studio's studio_status arrives as mcp__unsloth_studio_studio_status: the
    server is 'unsloth-studio' and the tool 'studio_status', NOT 'unsloth_studio_studio_status'
    (which a naive split('__') yields). Handle the underscore form, the hyphen+double-underscore
    form (mcp__unsloth-studio__studio_status), and a generic double-underscore fallback.
    """
    rest = tool_name[len("mcp__"):] if tool_name.startswith("mcp__") else tool_name
    if "__" in rest:                          # hyphen server (unsloth-studio__<tool>); '__' is the delimiter
        server, _, tool = rest.partition("__")
        return server, tool
    t = rest.split("_")                       # all-underscore: 2-token server 'unsloth-studio' + tool (may hold '_')
    if len(t) >= 3 and t[0] == "unsloth":
        return t[0] + "-" + t[1], "_".join(t[2:])
    parts = rest.split("__")
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return rest, rest


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "post"
    # Claude Code sends UTF-8 JSON. Read bytes and decode explicitly: on Windows, sys.stdin would
    # otherwise use the ANSI code page (cp1252) and garble or reject non-ASCII text.
    stream = getattr(sys.stdin, "buffer", None)
    raw = stream.read().decode("utf-8", "replace") if stream is not None else ""
    try:
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}
    tool_name = str(event.get("tool_name", ""))
    if not tool_name.startswith(SERVER_PREFIX):
        return
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
    logs = root / "logs"
    pending = logs / ".pending"
    pending.mkdir(parents=True, exist_ok=True)
    tuid = str(event.get("tool_use_id") or "")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", tuid) or hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    now = time.time()

    if mode == "pre":
        (pending / (safe_id + ".json")).write_text(json.dumps({"t_start": now}), encoding="utf-8")
        return

    t_start = None
    pfile = pending / (safe_id + ".json")
    if pfile.exists():
        try:
            t_start = json.loads(pfile.read_text(encoding="utf-8")).get("t_start")
        except Exception:
            t_start = None
        try:
            pfile.unlink()
        except Exception:
            pass

    server, tool = split_server_tool(tool_name)
    response = None
    for key in ("tool_response", "tool_output", "tool_result", "response", "error"):
        if key in event:
            response = event[key]
            break
    args = expand(event.get("tool_input"))
    result = expand(response)
    ok = (mode != "fail") and not looks_like_error(result)
    if isinstance(result, list):
        ok = ok and not any(looks_like_error(x) for x in result if isinstance(x, dict))

    record = {
        "seq": None,
        "ts_start": iso(t_start),
        "ts_end": iso(now),
        "t_start": round(t_start, 3) if t_start else None,
        "t_end": round(now, 3),
        "duration_s": round(now - t_start, 3) if t_start else None,
        "ok": ok,
        "event": mode,
        "server": server,
        "tool": tool,
        "tool_use_id": tuid,
        "args": clean(args, LINE_STR_MAX),
        "ids": find_ids(result),
        "media": find_media(result),
        "result": None,
        "session_id": event.get("session_id"),
    }
    summary = json.dumps(clean(result, LINE_STR_MAX), ensure_ascii=False)
    record["result"] = summary if len(summary) <= RESULT_MAX else summary[:RESULT_MAX] + "...<truncated>"
    raw_payload = {
        "tool_name": tool_name,
        "ts_start": record["ts_start"],
        "ts_end": record["ts_end"],
        "ok": ok,
        "args": clean(args, RAW_STR_MAX),
        "result": clean(result, RAW_STR_MAX),
    }
    locked_append(logs, record, raw_payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
            (root / "logs").mkdir(parents=True, exist_ok=True)
            with open(root / "logs" / "hook_errors.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + traceback.format_exc() + "\n")
        except Exception:
            pass
    sys.exit(0)
