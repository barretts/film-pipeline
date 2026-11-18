"""Loopback CPU project API and local human review. Never starts the legacy GPU queue."""
import argparse
import json
import secrets
import threading
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .projects import FilmProjects, ROOT
from .project_contract import ProjectError

REVIEW_PAGE = Path(__file__).with_name('project_review.html').read_text(encoding='utf8')


class FilmHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, projects, origins=()):
        if address[0] != '127.0.0.1':
            raise ValueError('Film API must bind to 127.0.0.1')
        self.projects = projects
        self.review_token = secrets.token_urlsafe(32)
        self.origins = set(origins)
        super().__init__(address, FilmHandler)
        self.origins.update({f'http://127.0.0.1:{self.server_port}', f'http://localhost:{self.server_port}'})


class FilmHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Request bodies, scripts and review capabilities do not belong in access logs.

    def headers_for(self, content_type, length):
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        origin = self.headers.get('Origin')
        if origin in self.server.origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def check_origin(self):
        if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            raise ProjectError('Local Host header required', 403)
        if self.headers.get('Origin') and self.headers['Origin'] not in self.server.origins:
            raise ProjectError('Origin is not allowed', 403)

    def json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf8')
        self.send_response(status); self.headers_for('application/json; charset=utf-8', len(data))
        self.end_headers(); self.wfile.write(data)

    def body(self):
        if self.headers.get_content_type() != 'application/json':
            raise ProjectError('Use application/json')
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise ProjectError('Invalid content length')
        if not 0 < size <= 2_000_000:
            raise ProjectError('Request body missing or too large')
        return json.loads(self.rfile.read(size), parse_constant=lambda s: (_ for _ in ()).throw(ProjectError('Non-finite JSON value')))

    def do_OPTIONS(self):
        try:
            self.check_origin()
            self.send_response(204)
            self.headers_for('text/plain', 0)
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        except ProjectError as e:
            self.json({'error': str(e)}, e.status)

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        try:
            self.check_origin()
            path = urllib.parse.urlsplit(self.path).path
            parts = path.strip('/').split('/')
            projects = self.server.projects
            prefix = ['api', 'film', 'v1', 'projects']
            if method == 'GET' and path == '/api/film/v1/capabilities':
                self.json({'schema_version': 1, 'gpu_policy': 'disabled', 'inference': 'local-cpu-only',
                           'account_required': False, 'human_approval': 'local-review-page',
                           'manual_gpu_worker': 'separate-cli-explicit-opt-in'}); return
            if parts == prefix:
                if method == 'GET':
                    self.json([projects.get(p['project_id']) for p in projects.store.list()]); return
                body = self.body()
                spec = body.get('spec')
                if body.get('template') == 'signal-in-the-snow':
                    spec = json.loads((ROOT / 'examples/signalInTheSnow.json').read_text(encoding='utf8'))
                project = projects.create(spec, body.get('creation_id'))
                self.json(projects.get(project['project_id']), 201); return
            if len(parts) >= 5 and parts[:4] == prefix:
                project_id = parts[4]
                if method == 'GET' and len(parts) == 5:
                    self.json(projects.get(project_id)); return
                if method == 'POST' and len(parts) == 6 and parts[5] == 'commands':
                    self.json(projects.command(project_id, self.body())); return
                if method == 'GET' and len(parts) == 7 and parts[5] == 'artifacts':
                    target, item = projects.artifact(project_id, parts[6])
                    self.send_artifact(target, item); return
            if method == 'GET' and (path == '/' or (len(parts) == 4 and parts[:2] == ['film', 'projects'] and parts[3] == 'review')):
                if path != '/':
                    projects.get(parts[2])
                data = REVIEW_PAGE.replace('__REVIEW_TOKEN__', self.server.review_token).encode('utf8')
                self.send_response(200); self.headers_for('text/html; charset=utf-8', len(data))
                self.send_header('Set-Cookie', 'filmReview=' + self.server.review_token + '; HttpOnly; SameSite=Strict; Path=/')
                self.end_headers(); self.wfile.write(data); return
            if method == 'POST' and len(parts) == 4 and parts[:2] == ['film', 'projects'] and parts[3] == 'commands':
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                cookie = cookies.get('filmReview')
                if (not cookie or not secrets.compare_digest(cookie.value, self.server.review_token) or
                        not secrets.compare_digest(self.headers.get('X-Film-Review', ''), self.server.review_token)):
                    raise ProjectError('Open the local review page to make this decision', 403)
                self.json(projects.command(parts[2], self.body(), human=True)); return
            raise ProjectError('Not found', 404)
        except (ProjectError, ValueError, TypeError, KeyError) as e:
            self.json({'error': str(e)}, getattr(e, 'status', 400))
        except ConnectionError:
            pass
        except Exception:
            self.json({'error': 'Local film operation failed; inspect its command status and files'}, 500)

    def send_artifact(self, target, item):
        size = target.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get('Range')
        if requested:
            import re
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
            if not match or not any(match.groups()):
                raise ProjectError('Unsupported byte range', 416)
            a, b = match.groups()
            start, end = (int(a), min(int(b), end) if b else end) if a else (max(0, size-int(b)), end)
            if start > end or start >= size:
                raise ProjectError('Range outside artifact', 416)
        self.send_response(206 if requested else 200)
        self.headers_for(item['media_type'], end-start+1)
        self.send_header('Accept-Ranges', 'bytes')
        if requested:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        with target.open('rb') as stream:
            stream.seek(start); remaining = end-start+1
            while remaining:
                block = stream.read(min(remaining, 262144))
                if not block:
                    break
                self.wfile.write(block); remaining -= len(block)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--root', type=Path, default=ROOT / 'film-projects')
    parser.add_argument('--stop-file', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--toonflow-origin', action='append', default=['http://127.0.0.1:33030', 'http://localhost:33030'])
    args = parser.parse_args()
    for origin in args.toonflow_origin:
        parsed = urllib.parse.urlsplit(origin)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.path:
            parser.error('Toonflow origins must be local HTTP origins')
    projects = FilmProjects(args.root)
    server = FilmHTTPServer(('127.0.0.1', args.port), projects, args.toonflow_origin)
    worker = threading.Thread(target=projects.serve, daemon=True, name='film-cpu-worker')
    worker.start()
    if args.stop_file:
        def watch_stop():
            while not projects.stop.wait(0.2):
                if args.stop_file.exists():
                    projects.stop.set(); projects.wake.set(); server.shutdown(); return
        threading.Thread(target=watch_stop, daemon=True, name='film-cpu-stop').start()
    print(f'CPU film projects: http://127.0.0.1:{server.server_port}/ — GPU disabled', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        projects.stop.set(); projects.wake.set(); server.server_close(); worker.join(timeout=10)


if __name__ == '__main__':
    main()
