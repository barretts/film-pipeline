#!/usr/bin/env python3
"""Check a rendered vertical reel and confirm that its narration is present.

This checks stream properties, decode, broad Windows read access, audio match,
and sampled visual changes. It does not assess caption content or lip-sync.
"""

import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy import signal

RATE = 8000


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def audio_samples(path):
    result = command(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                      "-ar", str(RATE), "-f", "f32le", "-"])
    return np.frombuffer(result.stdout, dtype="<f4")


def best_audio_match(mix, voice, rate=RATE):
    if len(voice) == 0 or len(mix) < len(voice):
        return None
    voice = voice.astype(np.float64)
    voice -= voice.mean()
    energy = np.dot(voice, voice)
    if energy < 1e-12:
        return None
    mix = mix.astype(np.float64)
    correlation = signal.correlate(mix, voice, mode="valid", method="fft")
    squares = np.concatenate(([0.0], np.cumsum(mix * mix)))
    sums = np.concatenate(([0.0], np.cumsum(mix)))
    n = len(voice)
    local = (squares[n:] - squares[:-n]) - (sums[n:] - sums[:-n]) ** 2 / n
    scale = np.sqrt(np.maximum(local, 0) * energy)
    scores = np.divide(correlation, scale, out=np.zeros_like(correlation), where=scale > 1e-12)
    offset = int(np.argmax(scores))
    return {"correlation": float(scores[offset]), "offset_seconds": offset / rate}


def broad_windows_read(path):
    if os.name != "nt":
        return None
    script = r"""
    $acl = Get-Acl -LiteralPath $env:REEL_QA_PATH
    $allow = $false; $deny = $false
    foreach ($rule in $acl.Access) {
      try { $sid = $rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value } catch { continue }
      if ($sid -in @('S-1-1-0','S-1-5-11','S-1-5-32-545') -and (([int]$rule.FileSystemRights -band 1) -ne 0)) {
        if ($rule.AccessControlType -eq 'Allow') { $allow = $true }
        if ($rule.AccessControlType -eq 'Deny') { $deny = $true }
      }
    }
    if ($allow -and -not $deny) { 'read-allowed' } else { 'not-established' }
    """
    env = dict(os.environ, REEL_QA_PATH=str(path))
    result = command(["powershell", "-NoProfile", "-Command", script], env=env, text=True,
                     encoding="utf-8", errors="replace")
    return result.stdout.strip() == "read-allowed"


def visual_changes(path):
    result = command(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "fps=2,scale=90:160,format=gray",
                      "-f", "rawvideo", "-"])
    frame_size = 90 * 160
    if len(result.stdout) % frame_size:
        raise ValueError("partial video frame during visual scan")
    frames = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 160, 90).astype(np.float32)
    if len(frames) < 2:
        return {"sampled_frames": len(frames), "largest_change": 0.0, "changes_over_6": 0}
    differences = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    return {"sampled_frames": len(frames), "largest_change": float(differences.max()),
            "changes_over_6": int(np.count_nonzero(differences >= 6.0))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--speech", required=True, type=Path, help="Original narration used in the reel")
    parser.add_argument("--min-duration", type=float, default=3.0)
    parser.add_argument("--max-duration", type=float, default=90.0)
    parser.add_argument("--min-audio-match", type=float, default=0.2)
    args = parser.parse_args()
    errors = []
    report = {"video": str(args.video.resolve()), "speech": str(args.speech.resolve()), "errors": errors}
    try:
        if not args.video.is_file() or not args.speech.is_file():
            raise ValueError("video and source speech must both exist")
        if not all(shutil.which(name) for name in ("ffmpeg", "ffprobe")):
            raise ValueError("ffmpeg and ffprobe must be on PATH")
        raw = command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(args.video)])
        info = json.loads(raw.stdout)
        video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
        duration = float(info["format"]["duration"])
        report["streams"] = {"video_codec": video.get("codec_name"), "width": video.get("width"),
                             "height": video.get("height"), "pixel_format": video.get("pix_fmt"),
                             "fps": video.get("r_frame_rate"), "audio_codec": audio.get("codec_name"),
                             "channels": audio.get("channels"), "sample_rate": audio.get("sample_rate"),
                             "duration_seconds": duration}
        if video.get("codec_name") != "h264" or (video.get("width"), video.get("height")) != (1080, 1920):
            errors.append("video must be H.264 at 1080x1920")
        if video.get("pix_fmt") != "yuv420p":
            errors.append("video must use broadly compatible yuv420p pixel format")
        try:
            fps = float(Fraction(video.get("r_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        if fps < 30.0:
            errors.append("video must be at least 30 frames per second")
        if audio.get("codec_name") != "aac" or audio.get("channels") != 2:
            errors.append("audio must be stereo AAC")
        if not args.min_duration <= duration <= args.max_duration:
            errors.append("duration is outside the requested bounds")
        command(["ffmpeg", "-v", "error", "-xerror", "-i", str(args.video), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
        report["full_decode"] = True
        report["windows_broad_read"] = broad_windows_read(args.video)
        if report["windows_broad_read"] is False:
            errors.append("Windows ACL does not establish read access for Users or Authenticated Users")
        mix, voice = audio_samples(args.video), audio_samples(args.speech)
        report["audio_rms"] = float(np.sqrt(np.mean(np.square(mix)))) if len(mix) else 0.0
        if report["audio_rms"] < 0.0001:
            errors.append("rendered audio is silent")
        report["narration_match"] = best_audio_match(mix, voice)
        if report["narration_match"] is None or report["narration_match"]["correlation"] < args.min_audio_match:
            errors.append("source narration was not detected in the mixed audio")
        report["visual_change"] = visual_changes(args.video)
        if report["visual_change"]["changes_over_6"] < 1:
            errors.append("no substantial visual transition detected in two-frames-per-second samples")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"check failed: {exc}")
    report["ok"] = not errors
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
