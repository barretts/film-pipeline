"""Provide HTTPS access to exactly one Blender MP4 for the lifetime of a render."""
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
from queue import Empty, Queue
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit


def file_handler(route, data):
    class GuideHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self.serve(False)

        def do_GET(self):
            self.serve(True)

        def serve(self, body):
            if self.path != route:
                self.send_error(404)
                return
            span = self.headers.get("Range")
            start, stop = 0, len(data)
            if span:
                match = re.fullmatch(r"bytes=(\d*)-(\d*)", span)
                if match and any(match.groups()):
                    left, right = match.groups()
                    if left:
                        start = int(left)
                        stop = min(stop, int(right)+1) if right else stop
                    else:
                        start = max(0, stop-int(right))
                else:
                    start = stop
                if start >= stop:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(data)}")
                    self.end_headers()
                    return
            self.send_response(206 if span else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(stop-start))
            if span:
                self.send_header("Content-Range", f"bytes {start}-{stop-1}/{len(data)}")
            self.end_headers()
            if body:
                self.wfile.write(data[start:stop])

    return GuideHandler


def verify_url(url, guide):
    if urlsplit(url).scheme != "https":
        raise ValueError("The video reference must have an HTTPS URL")
    with urllib.request.urlopen(url, timeout=15) as response:
        size = guide.stat().st_size
        other = response.read(size+1)
        if len(other) != size or hashlib.sha256(other).digest() != hashlib.sha256(guide.read_bytes()).digest():
            raise ValueError("The HTTPS reference does not contain the exported guide MP4")


@contextmanager
def temporary_link(guide):
    exe = shutil.which("cloudflared")
    if not exe:
        raise ValueError("Install cloudflared or pass --reference-url with the HTTPS URL of this guide")
    route = "/" + secrets.token_urlsafe(32) + "/guide.mp4"
    server = ThreadingHTTPServer(("127.0.0.1", 0), file_handler(route, Path(guide).read_bytes()))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tunnel = None
    try:
        address = f"http://127.0.0.1:{server.server_port}"
        cmd = [exe, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", address]
        env = {k:v for k,v in os.environ.items() if k.upper() != "OPENROUTER_API_KEY"}
        tunnel = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        links = Queue()
        def read_log():
            for line in tunnel.stdout:
                match = re.search(rb"https://[a-z0-9-]+\.trycloudflare\.com\b", line)
                if match:
                    links.put(match[0].decode())
            links.put(None)
        thread = threading.Thread(target=read_log, daemon=True)
        thread.start()
        try:
            origin = links.get(timeout=45)
        except Empty:
            raise TimeoutError("Cloudflare did not issue a temporary HTTPS address") from None
        if not origin:
            raise RuntimeError("Cloudflare exited before creating the temporary link")
        url = origin + route
        for attempt in range(15):
            try:
                verify_url(url, guide)
                break
            except (OSError, ValueError):
                if attempt == 14:
                    raise RuntimeError("The temporary HTTPS link did not serve the guide") from None
                time.sleep(2)
        yield url
    finally:
        if tunnel is not None:
            if tunnel.poll() is None:
                tunnel.terminate()
                try:
                    tunnel.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tunnel.kill()
                    tunnel.wait()
            tunnel.stdout.close()
        server.shutdown()
        server.server_close()
