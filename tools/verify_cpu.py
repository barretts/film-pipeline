"""Run local-film regressions with a real process/network/write firewall around the suite."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    run = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix='film-cpu-verification-')).resolve()
    run.mkdir(parents=True, exist_ok=True)
    scratch = run / 'scratch'; scratch.mkdir(exist_ok=True)
    (scratch / 'jobs').mkdir(exist_ok=True)
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', TEMP=str(scratch), TMP=str(scratch))
    tempfile.tempdir = str(scratch)
    os.chdir(scratch)
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests'), str(ROOT / 'tools')]
    blocked, processes, sockets = [], {}, []
    def inside(path):
        try: return Path(os.fsdecode(path)).resolve().is_relative_to(run)
        except (TypeError, ValueError, OSError): return False
    def reject(event):
        blocked.append(event)
        raise PermissionError('CPU verification firewall blocked ' + event)
    def audit(event, values):
        if event == 'open':
            path, mode, flags = values
            write = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
            if write and not isinstance(path, int) and not inside(path): reject(event)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'shutil.rmtree'):
            if not inside(values[0]): reject(event)
        elif event in ('os.rename', 'os.replace', 'os.link', 'os.symlink'):
            if not inside(values[0]) or not inside(values[1]): reject(event)
        elif event in ('os.system', 'os.startfile', 'os.exec'):
            reject(event)
        elif event == 'subprocess.Popen':
            executable, argv = values[:2]
            if executable is None:
                executable = re.match(r'^\s*(?:"([^"]+)"|(\S+))', argv).groups()
                executable = next(x for x in executable if x)
            name = Path(executable).stem.lower()
            command = str(argv).lower()
            if name not in ('ffmpeg', 'ffprobe') or any(word in command for word in ('cuda','cuvid','nvenc','vulkan','opencl','opengl','d3d11','dxva','qsv','amf','hwaccel','http://','https://')):
                reject(event + ':' + name)
            processes[name] = processes.get(name, 0) + 1
        elif event == 'socket.bind':
            sock, address = values
            if address[0] != '127.0.0.1' or address[1] != 0: reject(event)
            sockets.append(sock)
        elif event == 'socket.connect':
            address = values[1]; ports = set()
            for sock in sockets:
                try: ports.add(sock.getsockname()[1])
                except OSError: pass
            if address[0] not in ('127.0.0.1', 'localhost') or address[1] not in ports: reject(event)
        elif event == 'socket.getaddrinfo':
            if values[0] not in ('127.0.0.1', 'localhost'): reject(event)
    sys.addaudithook(audit)
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / 'tests'), pattern='test_local_film*.py')
    import test_minimax_speech
    test_minimax_speech.ROOT = scratch
    suite.addTests(loader.loadTestsFromModule(test_minimax_speech))
    start = time.monotonic()
    with (run / 'unittest.log').open('w', encoding='utf8') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    summary = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'skipped': len(result.skipped), 'seconds': round(time.monotonic()-start, 2),
               'blocked_operations': blocked, 'processes': processes, 'log': str(run / 'unittest.log')}
    (run / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(json.dumps(summary, indent=2))
    if not result.wasSuccessful():
        print((run / 'unittest.log').read_text(encoding='utf8')[-18000:])
    raise SystemExit(0 if result.wasSuccessful() and not blocked else 1)


if __name__ == '__main__': main()
