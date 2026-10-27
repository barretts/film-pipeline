#!/usr/bin/env python3
"""Lip-sync a face image or moving video to speech using local MuseTalk 1.5."""

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "tools" / "MuseTalk"
PYTHON = ROOT / "venvs" / "musetalk" / "Scripts" / "python.exe"


class LipSyncError(Exception):
    pass


def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LipSyncError(f"Command failed: {command[0]}: {exc}") from exc


def probe(path):
    result = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                 capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise LipSyncError("ffprobe returned invalid JSON") from exc


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--image", type=Path, help="Portrait image with a visible face")
    source_group.add_argument("--video", type=Path, help="Moving video with a visible face, at least as long as the speech")
    parser.add_argument("--audio", required=True, type=Path, help="Speech audio")
    parser.add_argument("--out", required=True, type=Path, help="Output MP4")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        visual, audio, output = (p.resolve() for p in (args.image or args.video, args.audio, args.out))
        if args.image and (visual.suffix.lower() not in (".png", ".jpg", ".jpeg") or not visual.is_file()):
            raise LipSyncError("--image must be an existing PNG or JPEG portrait")
        if args.video and not visual.is_file():
            raise LipSyncError("--video must be an existing video file")
        if not audio.is_file():
            raise LipSyncError("--audio must be an existing audio file")
        if output.suffix.lower() != ".mp4" or output in (visual, audio):
            raise LipSyncError("--out must be an MP4 path distinct from the inputs")
        if output.exists() and not args.overwrite:
            raise LipSyncError("output already exists; use --overwrite to replace it")
        if not PYTHON.is_file() or not (ENGINE / "models" / "musetalkV15" / "unet.pth").is_file():
            raise LipSyncError("MuseTalk environment or weights missing; see TOOLS.md")
        if any(not shutil.which(tool) for tool in ("ffmpeg", "ffprobe")):
            raise LipSyncError("ffmpeg and ffprobe must be on PATH")
        # The upstream engine passes intermediate paths to the shell unquoted.
        if any(char in str(ROOT) for char in ' \t\r\n&()^%!"<>|'):
            raise LipSyncError("project path contains characters unsupported by MuseTalk's Windows shell commands")
        source_info = probe(audio)
        if not any(s.get("codec_type") == "audio" for s in source_info.get("streams", [])):
            raise LipSyncError("input does not contain audio")
        if args.video:
            video_info = probe(visual)
            source_video = next((s for s in video_info.get("streams", []) if s.get("codec_type") == "video"), None)
            if source_video is None:
                raise LipSyncError("--video does not contain a video stream")
        jobs = ROOT / "jobs"
        logs = ROOT / "logs"
        jobs.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        log = logs / f"lipsync-{time.time_ns()}.log"
        with tempfile.TemporaryDirectory(prefix="muse-", dir=jobs) as temporary:
            work = Path(temporary)
            voice = work / "voice.wav"
            run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(audio),
                 "-vn", "-c:a", "pcm_s16le", str(voice)])
            try:
                expected = float(probe(voice)["format"]["duration"])
                if not math.isfinite(expected) or expected <= 0:
                    raise ValueError("invalid audio duration")
            except (KeyError, ValueError, TypeError) as exc:
                raise LipSyncError("could not verify speech duration") from exc
            if args.video:
                try:
                    duration = float(source_video["duration"])
                    if not math.isfinite(duration) or duration <= 0:
                        raise ValueError("invalid video duration")
                except (KeyError, ValueError, TypeError) as exc:
                    raise LipSyncError("could not verify source video stream duration") from exc
                if duration + 0.001 < expected:
                    raise LipSyncError(f"source video is shorter than speech ({duration:.3f}s vs {expected:.3f}s); looping is not allowed")
                portrait = work / "source.mp4"
                # A constant frame rate preserves the input's forward motion and
                # prevents MuseTalk's frame-indexing from reversing short clips.
                run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(visual),
                     "-map", "0:v:0", "-an", "-vf", "fps=25", "-t", f"{expected:.9f}",
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(portrait)])
                staged_info = probe(portrait)
                staged_video = next((s for s in staged_info.get("streams", []) if s.get("codec_type") == "video"), {})
                try:
                    staged_frames = int(staged_video["nb_frames"])
                except (KeyError, ValueError, TypeError) as exc:
                    raise LipSyncError("could not verify staged source video frame count") from exc
                if staged_frames < math.floor(expected * 25):
                    raise LipSyncError("decoded source video has fewer frames than needed; looping is not allowed")
            else:
                portrait = work / ("portrait" + visual.suffix.lower())
                shutil.copyfile(visual, portrait)
            config = work / "config.json"
            config.write_text(json.dumps({"task": {"video_path": portrait.as_posix(),
                "audio_path": voice.as_posix(), "result_name": "talking.mp4"}}), encoding="utf-8")
            env = dict(os.environ, HF_HOME=str(ROOT / "venvs" / "hf-cache"),
                       TORCH_HOME=str(ROOT / "venvs" / "torch-cache"),
                       HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONIOENCODING="utf-8")
            command = [str(PYTHON), "-u", "-m", "scripts.inference", "--inference_config", str(config),
                       "--unet_config", "models/musetalkV15/musetalk.json", "--unet_model_path",
                       "models/musetalkV15/unet.pth", "--whisper_dir", "models/whisper",
                       "--result_dir", str(work / "result"), "--use_float16", "--batch_size", "4", "--fps", "25"]
            print(f"Running local MuseTalk; detailed log: {log}", flush=True)
            with log.open("w", encoding="utf-8") as stream:
                run(command, cwd=ENGINE, env=env, stdout=stream, stderr=subprocess.STDOUT)
            result = work / "result" / "v15" / "talking.mp4"
            if not result.is_file() or result.stat().st_size == 0:
                raise LipSyncError(f"MuseTalk produced no video; inspect {log}")
            info = probe(result)
            streams = info.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), None)
            if not video or not any(s.get("codec_type") == "audio" for s in streams):
                raise LipSyncError(f"MuseTalk output is missing video or audio; inspect {log}")
            try:
                actual = float(info["format"]["duration"])
                video_duration = float(video["duration"])
            except (KeyError, ValueError, TypeError) as exc:
                raise LipSyncError("could not verify output duration") from exc
            if abs(actual - expected) > 0.15 or abs(video_duration - expected) > 0.15:
                raise LipSyncError(f"video or output duration does not match audio {expected:.2f}s")
            run(["ffmpeg", "-v", "error", "-xerror", "-i", str(result), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
            fd, name = tempfile.mkstemp(prefix=".lipsync-", suffix=".mp4", dir=output.parent)
            os.close(fd)
            staged = Path(name)
            try:
                shutil.copyfile(result, staged)
                if output.exists() and not args.overwrite:
                    raise LipSyncError("output appeared during rendering")
                os.replace(staged, output)
            finally:
                staged.unlink(missing_ok=True)
        print(f"Wrote {output} ({actual:.2f}s); log: {log}")
        return 0
    except (LipSyncError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
