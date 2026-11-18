"""OpenRouter access for the opt-in cloud steering workflow."""
import json
import os
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from uuid import uuid4

from takefive.script import digest, dump


LUNA = "openai/gpt-6-luna"
HEYGEN = "heygen/heygen-video-1"
API = "https://openrouter.ai/api/v1"


def save(path, value):
    temp = path.with_name(f".{path.name}-{uuid4().hex}.tmp")
    try:
        dump(temp, value)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_key(env_file):
    if env_file:
        for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
            match = re.fullmatch(r"\s*(?:export\s+)?OPENROUTER_API_KEY\s*=\s*(.*?)\s*", line)
            if match:
                value = match[1]
                if value[:1] in ("'", '"') and value[-1:] == value[:1]:
                    value = value[1:-1]
                if value:
                    return value
    else:
        value = os.environ.get("OPENROUTER_API_KEY")
        if value:
            return value
    raise ValueError("Set OPENROUTER_API_KEY or pass --env-file with an OpenRouter key.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def safe_message(value):
    message = re.sub(r"data:[^\s\x22]+|https?://[^\s\x22]+|sk-or-[\w-]+", "[redacted]", str(value))
    return message[:1000]


class RouterError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"OpenRouter HTTP {code}: {safe_message(message)}")


class OpenRouter:
    def __init__(self, env_file=None):
        self.key = read_key(env_file)
        self.http = urllib.request.build_opener(NoRedirect())

    def open(self, path, body=None, download=False):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Expected an OpenRouter API path")
        headers = {"Authorization": "Bearer " + self.key, "User-Agent": "TakeFive/1.0"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(API + path, data=data, headers=headers)
        try:
            return self.http.open(req, timeout=180)
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location", "")
            if download and error.code in (301, 302, 303, 307, 308) and urlsplit(location).scheme == "https":
                # Media CDNs authorize the download in the URL itself.
                error.close()
                return urllib.request.urlopen(location, timeout=180)
            with error:
                raw = error.read(3000).decode(errors="replace")
            try:
                detail = json.loads(raw)["error"]
                message = detail.get("message", detail) if isinstance(detail, dict) else detail
            except (ValueError, KeyError, TypeError):
                message = raw
            raise RouterError(error.code, message) from None

    def json(self, path, body=None):
        with self.open(path, body) as response:
            return json.load(response)

    def download(self, path, dest):
        with self.open(path, download=True) as response, dest.open("wb") as stream:
            shutil.copyfileobj(response, stream)


def check_shape(answer, schema):
    """Validate the closed objects, bounded lists, strings and enums used by the director."""
    kind = schema["type"]
    if kind == "object" and isinstance(answer, dict) and set(answer) == set(schema["properties"]):
        for key, child in schema["properties"].items():
            check_shape(answer[key], child)
    elif kind == "array" and isinstance(answer, list) and schema["minItems"] <= len(answer) <= schema["maxItems"]:
        for value in answer:
            check_shape(value, schema["items"])
    elif kind == "string" and isinstance(answer, str) and ("enum" not in schema or answer in schema["enum"]):
        return
    else:
        raise ValueError(f"Director returned an invalid {kind}")


class CloudPlanner:
    def __init__(self, router, model):
        self.router = router
        self.model = model
        self.receipts = []

    def ask(self, system, user, schema, seed, directory, tokens, check):
        payload = {
            "model": self.model, "seed": seed, "max_completion_tokens": max(2048, tokens * 2),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "reasoning": {"effort": "low"},
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "steering_plan", "strict": True, "schema": schema}},
        }
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (digest("openrouter-chat-v1", payload) + ".json")
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))
        else:
            print(f"Directing with {self.model} (request {len(self.receipts) + 1}).", flush=True)
            reply = self.router.json("/chat/completions", payload)
            choice = reply["choices"][0]
            receipt = {"id": reply["id"], "model": reply["model"], "provider": reply.get("provider"),
                       "usage": reply.get("usage", {}), "finish_reason": choice["finish_reason"]}
            try:
                answer = json.loads(choice["message"].get("content") or "")
                check_shape(answer, schema)
                check(answer)
            except (ValueError, TypeError, KeyError) as error:
                save(directory / (path.stem + "-rejected-" + uuid4().hex[:8] + ".json"), receipt)
                raise ValueError(f"{self.model} returned an incomplete or invalid plan: {error}") from error
            result = {"answer": answer, "receipt": receipt}
            save(path, result)
        check_shape(result["answer"], schema)
        check(result["answer"])
        self.receipts.append(result["receipt"])
        return result["answer"]
