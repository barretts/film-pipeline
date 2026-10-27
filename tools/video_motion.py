#!/usr/bin/env python3
"""Generate a local Wan image-to-video clip; resume the same Studio job safely."""

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

import studio_mcp

MODEL = "unsloth/Wan2.2-TI2V-5B-GGUF"


class MotionError(Exception):
    pass


def save_state(path, state):
    fd, temporary = tempfile.mkstemp(prefix=".motion-state-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def local_url(url):
    parts = urllib.parse.urlsplit(url or "")
    return parts.scheme == "http" and parts.hostname == "127.0.0.1" and parts.port == 8888


def verify_video(path, frames, fps, size):
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(path)],
                                capture_output=True, text=True, check=True, encoding="utf-8", errors="replace")
        info = json.loads(result.stdout)
        video = next(s for s in info.get("streams", []) if s.get("codec_type") == "video")
        width, height = (int(x) for x in size.split("x"))
        if (video.get("width"), video.get("height")) != (width, height):
            raise MotionError(f"unexpected video dimensions: {video.get('width')}x{video.get('height')}")
        actual_fps = float(Fraction(video["r_frame_rate"]))
        actual_frames = int(video.get("nb_read_frames") or video["nb_frames"])
        if abs(actual_fps - fps) > 0.001:
            raise MotionError(f"unexpected frame rate: {actual_fps}")
        if actual_frames < frames:
            raise MotionError(f"video has {actual_frames} frames, fewer than the requested {frames}")
        if float(video["duration"]) + 0.15 < frames / fps:
            raise MotionError("video is shorter than the requested frame count")
        subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                       capture_output=True, check=True)
        return {"width": width, "height": height, "duration_s": float(info["format"]["duration"]),
                "fps": video.get("r_frame_rate"), "frames": actual_frames}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, StopIteration, ZeroDivisionError) as exc:
        raise MotionError(f"cannot verify rendered video: {exc}") from exc


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--size", default="704x1280", choices=("704x1280", "1280x704"))
    parser.add_argument("--frames", type=int, default=73)
    parser.add_argument("--fps", type=int, default=16)
    parser.add_argument("--steps", type=int, default=16)
    parser.add_argument("--seed", type=int, default=2801)
    parser.add_argument("--wait-calls", type=int, default=120, help="maximum 30-second job observations per invocation")
    args = parser.parse_args()
    key = "\0"
    try:
        image, output = args.image.resolve(), args.out.resolve()
        if not image.is_file() or image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise MotionError("--image must name an existing PNG, JPEG or WebP image")
        if output.suffix.lower() != ".mp4" or output == image or output.exists():
            raise MotionError("--out must be a new MP4 path distinct from the input")
        if not (1 <= args.frames <= 1024 and 1 <= args.fps <= 120 and 1 <= args.steps <= 100 and args.wait_calls > 0):
            raise MotionError("frames, fps, steps or wait-calls outside supported bounds")
        output.parent.mkdir(parents=True, exist_ok=True)
        state_path = output.with_suffix(".wan-job.json")
        request = {"image": image.as_posix(), "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                   "prompt": args.prompt, "output": output.as_posix(), "size": args.size,
                   "frames": args.frames, "fps": args.fps, "steps": args.steps, "seed": args.seed}
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("request") != request:
                raise MotionError(f"state exists for different inputs: {state_path}")
            if state.get("phase") in ("submitting", "unknown_submit"):
                raise MotionError(f"submission outcome is unknown; inspect Studio recent video jobs before retrying: {state_path}")
            if state.get("phase") in ("failed", "cancelled", "complete"):
                raise MotionError(f"previous run is terminal ({state['phase']}): {state_path}")
        else:
            state = {"request": request, "phase": "new", "model": MODEL}
            save_state(state_path, state)
        key = studio_mcp.key_from_environment()
        api = studio_mcp.Studio(key, timeout=120)

        def call(name, payload):
            started = time.time()
            try:
                raw = api.rpc("tools/call", {"name": name, "arguments": payload})
                ok = not raw.get("isError", False)
            except Exception as exc:
                raw, ok = {"error": studio_mcp.safe(str(exc), key)}, False
            seq = studio_mcp.record_call(name, payload, raw, started, time.time(), key, ok)
            result = raw.get("structuredContent", raw)
            print(f"{name}: MCP sequence {seq}", flush=True)
            if not ok:
                raise MotionError(f"{name} failed: {json.dumps(studio_mcp.safe(result, key), ensure_ascii=True)}")
            return result

        def follow(kind, job):
            for _ in range(args.wait_calls):
                result = call("get_job", {"kind": kind, "id": job, "wait_s": 30, "return_media": "link"})
                status = result.get("status")
                print(f"{kind} {job}: {status}, progress {result.get('progress_percent')}", flush=True)
                if status in ("completed", "failed", "error", "cancelled"):
                    return result
            raise MotionError(f"{kind} job still active; resume using the same command: {job}")

        if state.get("phase") == "loading":
            job_id = state.get("load_job_id")
            if not job_id:
                raise MotionError(f"loading state lacks a job ID; inspect Studio before retrying: {state_path}")
            load = follow("load", job_id)
            if load.get("status") != "completed":
                state.update(phase="failed", error=studio_mcp.safe(load.get("error"), key))
                save_state(state_path, state)
                raise MotionError("model load failed; see state and MCP log")
            state["phase"] = "loaded"
            save_state(state_path, state)

        if state.get("phase") == "new":
            status = call("studio_status", {})
            if status.get("video", {}).get("generating") or status.get("image", {}).get("generating"):
                raise MotionError("another Studio image or video generation is active")
            load = call("load_model", {"model": MODEL, "kind": "video", "variant": "Q4_K_M",
                                       "memory_mode": "low_vram", "speed_mode": "off", "wait_s": 50})
            if load.get("status") == "loading":
                state.update(phase="loading", load_job_id=load.get("job_id"))
                save_state(state_path, state)
                if not state["load_job_id"]:
                    raise MotionError("Studio returned loading without a job ID")
                load = follow("load", state["load_job_id"])
                if load.get("status") != "completed":
                    state.update(phase="failed", error=studio_mcp.safe(load.get("error"), key))
                    save_state(state_path, state)
                    raise MotionError("model load failed; see state and MCP log")
            elif load.get("status") not in ("loaded", "completed"):
                raise MotionError(f"model did not load: {load.get('status')}")
            state["phase"] = "loaded"
            save_state(state_path, state)

        if state.get("phase") == "loaded":
            status = call("studio_status", {})
            if not status.get("video", {}).get("loaded"):
                state["phase"] = "new"
                save_state(state_path, state)
                raise MotionError("video model unloaded before submission; rerun the same command to load it")
            state["phase"] = "submitting"
            save_state(state_path, state)
            try:
                job = call("generate_video", {"prompt": args.prompt, "first_frame": {"path": image.as_posix()},
                           "num_frames": args.frames, "fps": args.fps, "steps": args.steps,
                           "size": args.size, "seed": args.seed})
            except Exception:
                state["phase"] = "unknown_submit"
                save_state(state_path, state)
                raise
            job_id = job.get("job_id") or job.get("id") or (job.get("video") or {}).get("id")
            if not job_id:
                state["phase"] = "unknown_submit"
                save_state(state_path, state)
                raise MotionError("generation response did not contain a job ID; inspect Studio before retrying")
            state.update(phase="generating", video_job_id=job_id)
            save_state(state_path, state)
            print(f"Video job: {job_id}; state: {state_path}", flush=True)

        result = follow("video", state["video_job_id"])
        if result.get("status") != "completed":
            state.update(phase="failed", error=studio_mcp.safe(result.get("error"), key))
            save_state(state_path, state)
            raise MotionError("generation failed; see state and MCP log")
        data = result.get("video") or {}
        url = data.get("download_url") or data.get("url")
        if not local_url(url):
            raise MotionError("completed job did not provide a verified local download URL")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        fd, temporary = tempfile.mkstemp(prefix=".motion-", suffix=".mp4", dir=output.parent)
        try:
            with os.fdopen(fd, "wb") as dst, opener.open(url, timeout=120) as src:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
            measurements = verify_video(Path(temporary), args.frames, args.fps, args.size)
            if output.exists():
                raise MotionError("output appeared during generation; refusing replacement")
            os.replace(temporary, output)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        state.update(phase="complete", measurements=measurements)
        save_state(state_path, state)
        print("WROTE", output, json.dumps(measurements), flush=True)
        try:
            call("unload_model", {"kind": "video"})
        except MotionError:
            print("Video saved but model unload could not be confirmed; check Studio state", file=sys.stderr)
        return 0
    except (MotionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print("error:", studio_mcp.safe(str(exc), key), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
