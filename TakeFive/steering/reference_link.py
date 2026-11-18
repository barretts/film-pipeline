"""Provide HTTPS access to exactly one Blender MP4 for the lifetime of a render."""
from contextlib import closing, contextmanager
import hashlib
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import IPv4Address
import json
import os
from pathlib import Path
from queue import Empty, Queue
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit


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


def read_tunnel_via_cloudflare(parts, limit):
    # A new quick-tunnel name can be negatively cached by the Windows resolver.
    host = parts.hostname
    query = urlencode({"name":host, "type":"A"})
    dns = urllib.request.Request("https://cloudflare-dns.com/dns-query?" + query,
                                 headers={"Accept":"application/dns-json"})
    with urllib.request.urlopen(dns, timeout=10) as response:
        records = json.load(response)
    address = next((a["data"] for a in records.get("Answer", [])
                    if a["type"] == 1 and IPv4Address(a["data"]).is_global), None)
    if not address:
        raise OSError(f"Cloudflare DNS has no public A record yet (status {records.get('Status')})")
    # Pin only the connection address. TLS still validates the tunnel's original hostname.
    context = ssl.create_default_context()
    with closing(HTTPSConnection(host, timeout=12, context=context)) as client:
        with socket.create_connection((address, 443), timeout=12) as tcp:
            client.sock = context.wrap_socket(tcp, server_hostname=host)
            client.request("GET", parts.path)
            with client.getresponse() as response:
                if response.status != 200:
                    raise OSError(f"Cloudflare returned HTTP {response.status} for the guide")
                return response.read(limit)


def verify_url(url, guide, *, quick_tunnel=False):
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("The video reference must have an HTTPS URL")
    size = guide.stat().st_size
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            other = response.read(size+1)
    except urllib.error.URLError as error:
        if (not quick_tunnel or not isinstance(error.reason, socket.gaierror)
                or not re.fullmatch(r"[a-z0-9-]+\.trycloudflare\.com", parts.hostname or "")):
            raise
        other = read_tunnel_via_cloudflare(parts, size+1)
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
        deadline = time.monotonic() + 120
        while True:
            try:
                verify_url(url, guide, quick_tunnel=True)
                break
            except (OSError, ValueError) as error:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"The temporary HTTPS link did not serve the guide: {error}") from None
                time.sleep(3)
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
