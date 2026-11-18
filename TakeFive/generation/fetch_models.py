"""Fetch the six published model files, with resumable transfers and LFS SHA-256 checks."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CHUNK = 64 * 1024 * 1024


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def fetch(item, root, libraries):
    filename = Path(item["path"]).name
    dest = root / item["folder"] / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = item["bytes"]
    if dest.exists():
        if dest.stat().st_size == expected and sha(dest) == item["sha256"]:
            print("Verified", filename, flush=True)
            return
        raise ValueError(f"Existing file failed checksum; preserved {dest}")
    partial = dest.with_suffix(".part")
    for library in libraries:
        source = library / item["folder"] / filename
        if source.is_file() and source.stat().st_size == expected and sha(source) == item["sha256"]:
            shutil.copyfile(source, partial)
            break
    url = f"https://huggingface.co/{item['repo']}/resolve/{item['revision']}/{item['path']}"
    last = 0
    size = partial.stat().st_size if partial.exists() else 0
    while size < expected:
        end = min(expected, size + CHUNK) - 1
        for attempt in range(5):
            try:
                # A fresh range-specific redirect avoids expired signed URLs on long downloads.
                req = Request(url + f"?download=true&chunk={size}&retry={attempt}", headers={"Range": f"bytes={size}-{end}", "Accept-Encoding": "identity"})
                with urlopen(req, timeout=120) as reply:
                    if reply.status == 206 and reply.headers.get("Content-Range") != f"bytes {size}-{end}/{expected}":
                        raise OSError(f"Unexpected range from model host for {filename}")
                    if reply.status != 206 and (reply.status != 200 or size != 0):
                        raise OSError(f"Model host did not resume {filename} at {size}")
                    with partial.open("ab") as sink:
                        shutil.copyfileobj(reply, sink, length=1024*1024)
                progressed = partial.stat().st_size
                if progressed <= size or progressed > expected:
                    raise OSError(f"Invalid transfer length in {partial}")
                size = progressed
                break
            except (OSError, HTTPError, URLError) as exc:
                if isinstance(exc, HTTPError) and exc.code in (401, 403, 404):
                    raise RuntimeError(f"{item['repo']} denied or could not find {filename} (HTTP {exc.code})") from exc
                if attempt == 4:
                    raise
                size = partial.stat().st_size if partial.exists() else 0
                if size >= expected:
                    break
                end = min(expected, size + CHUNK) - 1
                time.sleep(2 ** attempt)
        if size - last >= 2 * 1024**3:
            print(f"{filename}: {size / 1e9:.1f} / {expected / 1e9:.1f} GB", flush=True)
            last = size
    if partial.stat().st_size != expected or sha(partial) != item["sha256"]:
        raise ValueError(f"Checksum mismatch for {partial}; the file has not been installed.")
    os.replace(partial, dest)
    print("Installed and verified", filename, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1]/"runtime"/"generation-models")
    parser.add_argument("--reuse-library", type=Path, action="append", default=[])
    args = parser.parse_args()
    items = json.loads(Path(__file__).with_name("models.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda item: fetch(item, args.root, args.reuse_library), items))
