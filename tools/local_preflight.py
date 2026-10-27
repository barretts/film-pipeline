#!/usr/bin/env python3
"""Report local prerequisites before switching between coding and generation."""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def gpu_status():
    command = shutil.which("nvidia-smi")
    if not command:
        return {"available": False, "error": "nvidia-smi not found"}
    try:
        result = subprocess.run(
            [command, "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True,
        )
        devices = []
        for line in result.stdout.splitlines():
            name, total, used, free = (part.strip() for part in line.rsplit(",", 3))
            devices.append({"name": name, "total_mib": int(total),
                            "used_mib": int(used), "free_mib": int(free)})
        if not devices:
            return {"available": False, "error": "no GPU returned"}
        return {"available": True, "devices": devices}
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"available": False, "error": str(exc)}


def studio_health():
    # Bypass proxy settings: this request is strictly to the local machine.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open("http://127.0.0.1:8888/api/health", timeout=3) as response:
            payload = json.load(response)
        return {"reachable": True, "status": payload.get("status", "unknown")}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {"reachable": False, "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-free-mib", type=int, default=0,
                        help="Fail when no GPU has at least this much free memory")
    parser.add_argument("--require-studio", action="store_true",
                        help="Fail when the local Studio health endpoint is unavailable")
    parser.add_argument("--path", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="Path on the storage volume to check")
    args = parser.parse_args()
    if args.min_free_mib < 0:
        parser.error("--min-free-mib cannot be negative")
    try:
        disk = shutil.disk_usage(args.path)
    except OSError as exc:
        parser.error(f"cannot inspect path: {exc}")
    gpu = gpu_status()
    studio = studio_health()
    result = {
        "gpu": gpu,
        "studio": studio,
        "disk": {"path": str(args.path.resolve()), "free_bytes": disk.free},
        "commands": {name: shutil.which(name) for name in ("ffmpeg", "ffprobe", "unsloth", "omp")},
    }
    print(json.dumps(result, indent=2))
    if args.min_free_mib and not any(
        device["free_mib"] >= args.min_free_mib for device in gpu.get("devices", [])
    ):
        return 1
    if args.require_studio and (not studio["reachable"] or studio["status"] != "healthy"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
