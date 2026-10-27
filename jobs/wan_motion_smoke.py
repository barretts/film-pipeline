"""Run one local Wan image-to-video smoke; never print signed URLs or keys."""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import studio_mcp

KEY = studio_mcp.key_from_environment()
API = studio_mcp.Studio(KEY, timeout=120)


def call(name, args):
    start = time.time()
    try:
        response = API.rpc("tools/call", {"name": name, "arguments": args})
        ok = not response.get("isError", False)
    except Exception as exc:
        response, ok = {"error": str(exc).replace(KEY, "<redacted>")}, False
    seq = studio_mcp.record_call(name, args, response, start, time.time(), KEY, ok)
    content = response.get("structuredContent", response)
    if not ok:
        print("CALL FAILED", name, "seq", seq, json.dumps(studio_mcp.safe(content, KEY)), flush=True)
        raise RuntimeError("Studio call failed")
    print("CALL", name, "seq", seq, flush=True)
    return content


def follow(kind, job):
    for _ in range(180):
        state = call("get_job", {"kind": kind, "id": job, "wait_s": 30, "return_media": "link"})
        print("STATE", kind, state.get("status"), "progress", state.get("progress_percent"), flush=True)
        if state.get("status") in ("completed", "failed", "error", "cancelled"):
            return state
    raise RuntimeError(f"Job still active after bounded observation: {kind} {job}")


def main():
    model = "unsloth/Wan2.2-TI2V-5B-GGUF"
    state = call("studio_status", {})
    if state.get("video", {}).get("generating") or state.get("image", {}).get("generating"):
        raise RuntimeError("Another Studio image/video job is active")
    load = call("load_model", {"model": model, "kind": "video", "variant": "Q4_K_M",
                               "memory_mode": "low_vram", "speed_mode": "off", "wait_s": 50})
    if load.get("status") == "loading":
        job = load.get("job_id")
        print("LOAD_JOB", job, flush=True)
        load = follow("load", job)
        if load.get("status") != "completed":
            raise RuntimeError("Video model load failed")
    elif load.get("status") not in ("loaded", "completed"):
        raise RuntimeError("Unexpected load status " + str(load.get("status")))
    status = call("studio_status", {})
    video = status.get("video", {})
    print("VIDEO_CAPABILITIES", json.dumps(video, ensure_ascii=True), flush=True)
    if not video.get("loaded"):
        raise RuntimeError("Studio reports video model unloaded after load")
    presets = video.get("size_presets") or []
    portrait = next((p for p in presets if isinstance(p, str) and p in ("480x832", "512x768", "480x720")), None)
    args = {"prompt": "An adult woman looks left, raises her hand toward her face, turns her head and shoulders back to camera. Her hair and clothing move naturally. Fluid coherent animated character motion, same person, static camera.",
            "first_frame": {"path": (ROOT / "stills/reels/characters/03.png").as_posix()},
            "num_frames": 33, "fps": 16, "steps": 4, "seed": 2801, "return_media": "link"}
    if portrait:
        args["size"] = portrait
    # generate_video's schema does not accept return_media.
    args.pop("return_media")
    generated = call("generate_video", args)
    print("GENERATE_SUMMARY", json.dumps(studio_mcp.safe(generated, KEY)), flush=True)
    job = generated.get("job_id") or generated.get("id")
    if not job and isinstance(generated.get("video"), dict):
        job = generated["video"].get("id")
    if not job:
        raise RuntimeError("Generation did not return a job ID")
    print("VIDEO_JOB", job, flush=True)
    state = follow("video", job)
    if state.get("status") != "completed":
        print("VIDEO_TERMINAL", json.dumps(studio_mcp.safe(state, KEY)), flush=True)
        raise RuntimeError("Video generation failed")
    data = state.get("video") or {}
    url = data.get("download_url") or data.get("url")
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8888:
        raise RuntimeError("No verified local download URL returned")
    output = ROOT / "video/full_motion/wan-smoke.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError("Output already exists; refusing replacement")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=120) as src, output.open("xb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
    print("OUTPUT", output, "bytes", output.stat().st_size, flush=True)
    unload = call("unload_model", {"kind": "video"})
    print("UNLOADED", json.dumps(studio_mcp.safe(unload, KEY)), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ERROR", str(exc).replace(KEY, "<redacted>"), flush=True)
        sys.exit(1)
