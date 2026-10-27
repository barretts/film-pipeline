#!/usr/bin/env python3
"""Assemble existing local media into a simple pilot. No assets are generated.

Manifest paths are relative to the manifest file. Example::

    {"shots": [{"file": "../stills/shot.png", "type": "image", "duration": 4},
               {"file": "../video/shot.mp4", "type": "video", "duration": 3}],
     "audio": "../audio/pilot.wav"}

    python tools/assemble_pilot.py edit/pilot.json --out render/pilot.mp4

Shots are cuts in listed order. Audio starts at zero, is trimmed or padded with
silence, and video source audio is not used. This does not add titles, captions,
transitions, mixing, or verify provenance of facts present in supplied media.
"""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FPS = 24


class PilotError(Exception):
    pass


def run(command, cwd=None):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
    except OSError as exc:
        raise PilotError(f"Could not start {command[0]}: {exc}") from exc
    if result.returncode:
        raise PilotError(f"{command[0]} failed: {result.stderr.strip()[-3000:]}")
    return result.stdout


def probe(path):
    data = run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
                "-of", "json", str(path)])
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise PilotError(f"Invalid ffprobe output for {path}") from exc


def source_path(base, name):
    if not isinstance(name, str) or not name.strip():
        raise PilotError("Each media file must be a nonempty path")
    path = (base / name).resolve()
    if not path.is_file():
        raise PilotError(f"Media file not found: {path}")
    return path


def load_manifest(manifest):
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"Cannot read manifest: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"shots", "audio"}:
        raise PilotError("Manifest must contain only shots and audio")
    if not isinstance(data["shots"], list) or not data["shots"]:
        raise PilotError("Manifest needs at least one shot")
    shots = []
    for index, shot in enumerate(data["shots"], 1):
        if not isinstance(shot, dict) or set(shot) != {"file", "type", "duration"}:
            raise PilotError(f"Shot {index} must contain file, type and duration")
        if shot["type"] not in ("image", "video"):
            raise PilotError(f"Shot {index} type must be image or video")
        duration = shot["duration"]
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or duration < 1 / FPS):
            raise PilotError(f"Shot {index} duration must be at least 1/24 second")
        frames = round(duration * FPS)
        path = source_path(manifest.parent, shot["file"])
        info = probe(path)
        if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
            raise PilotError(f"Shot {index} has no video/image stream: {path}")
        if shot["type"] == "video":
            try:
                available = float(info["format"]["duration"])
            except (KeyError, ValueError, TypeError):
                raise PilotError(f"Cannot determine video duration for shot {index}") from None
            if not math.isfinite(available) or available + 0.001 < frames / FPS:
                raise PilotError(f"Shot {index} video is shorter than requested duration")
        shots.append((path, shot["type"], frames))
    audio = source_path(manifest.parent, data["audio"])
    if not any(stream.get("codec_type") == "audio" for stream in probe(audio).get("streams", [])):
        raise PilotError(f"Audio file has no audio stream: {audio}")
    return shots, audio


def assemble(manifest, output, width, height, overwrite=False):
    manifest, output = manifest.resolve(), output.resolve()
    if width < 2 or height < 2 or width % 2 or height % 2:
        raise PilotError("Width and height must be positive even numbers")
    if output.suffix.lower() != ".mp4":
        raise PilotError("Output must have an .mp4 extension")
    if output.exists() and not overwrite:
        raise PilotError(f"Output already exists (use --overwrite): {output}")
    shots, audio = load_manifest(manifest)
    if output in {manifest, audio, *(shot[0] for shot in shots)}:
        raise PilotError("Output must not overwrite the manifest or a source")
    output.parent.mkdir(parents=True, exist_ok=True)
    duration = sum(shot[2] for shot in shots) / FPS
    with tempfile.TemporaryDirectory(prefix="pilot-", dir=output.parent) as temp:
        work = Path(temp)
        for index, (source, kind, frames) in enumerate(shots):
            inputs = ["-loop", "1", "-framerate", str(FPS)] if kind == "image" else []
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                 *inputs, "-i", str(source), "-map", "0:v:0", "-an",
                 "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p",
                 "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                 "-crf", "20", "-threads", "2", str(work / f"shot{index:04}.mp4")])
        (work / "concat.txt").write_text("".join(
            f"file 'shot{index:04}.mp4'\n" for index in range(len(shots))), encoding="utf-8")
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-f", "concat", "-safe", "1", "-i", "concat.txt", "-c", "copy", "joined.mp4"], cwd=work)
        result = work / "result.mp4"
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(work / "joined.mp4"), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
             "-c:v", "copy", "-af", "apad", "-c:a", "aac", "-ar", "48000", "-ac", "2",
             "-t", f"{duration:.9f}", "-movflags", "+faststart", str(result)])
        info = probe(result)
        video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        sound = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
        try:
            actual = float(info["format"]["duration"])
        except (KeyError, TypeError, ValueError):
            raise PilotError("Output duration could not be verified") from None
        if (not video or not sound or video.get("codec_name") != "h264" or sound.get("codec_name") != "aac"
                or video.get("width") != width or video.get("height") != height
                or video.get("r_frame_rate") != f"{FPS}/1" or sound.get("sample_rate") != "48000"
                or sound.get("channels") != 2 or abs(actual - duration) > 0.1):
            raise PilotError("Output stream properties or duration did not match the requested pilot")
        # Create the staged file beside the destination so it inherits the
        # destination folder's permissions rather than the private temp folder's.
        fd, staged_name = tempfile.mkstemp(prefix=".pilot-", suffix=".mp4", dir=output.parent)
        os.close(fd)
        staged = Path(staged_name)
        try:
            shutil.copyfile(result, staged)
            if output.exists() and not overwrite:
                raise PilotError(f"Output appeared during rendering: {output}")
            os.replace(staged, output)
        finally:
            staged.unlink(missing_ok=True)
    return duration


def main():
    # A Windows console code page may not represent paths that FFmpeg accepts.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            parser.error(f"{tool} must be on PATH")
    try:
        duration = assemble(args.manifest, args.out, args.width, args.height, args.overwrite)
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.out.resolve()} ({duration:.2f}s, {args.width}x{args.height}, 24fps, stereo 48kHz)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
