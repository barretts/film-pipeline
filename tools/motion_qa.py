#!/usr/bin/env python3
"""Measure non-face changes in one continuous shot, after translation compensation.

This is evidence for review, not a verdict on actor motion, lip sync, or visual
quality. Cuts, camera zoom/rotation, lighting changes, overlays, tracking errors,
and deforming backgrounds can all affect the result. Use a single uncut shot,
inspect the frames, and specify a face exclusion large enough to cover the face
throughout the shot. Coordinates are normalized x,y,width,height in [0,1].
"""

import argparse
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
from scipy import ndimage


def rectangle(value):
    try:
        numbers = [float(item.strip()) for item in value.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected x,y,width,height") from exc
    if (len(numbers) != 4 or any(not math.isfinite(v) for v in numbers)
            or numbers[0] < 0 or numbers[1] < 0 or numbers[2] <= 0 or numbers[3] <= 0
            or numbers[0] + numbers[2] > 1 or numbers[1] + numbers[3] > 1):
        raise argparse.ArgumentTypeError("rectangle must lie within 0..1 and have positive width and height")
    return numbers


def bounds(rect, width, height):
    x, y, w, h = rect
    return (int(math.floor(x * width)), int(math.floor(y * height)),
            int(math.ceil((x + w) * width)), int(math.ceil((y + h) * height)))


def measurement_mask(width, height, exclude, region=None, margin=3):
    mask = np.zeros((height, width), dtype=bool)
    x0, y0, x1, y1 = bounds(region or [0, 0, 1, 1], width, height)
    mask[y0:y1, x0:x1] = True
    x0, y0, x1, y1 = bounds(exclude, width, height)
    mask[max(0, y0 - margin):min(height, y1 + margin),
         max(0, x0 - margin):min(width, x1 + margin)] = False
    if mask.sum() < width * height * 0.02:
        raise ValueError("region outside the excluded face is too small to analyze")
    return mask


def align_translation(first, second):
    """Estimate the integer translation that aligns second to first."""
    a = first.astype(np.float64)
    b = second.astype(np.float64)
    # High-pass removes the large DC component, while windowing reduces edge
    # discontinuities that otherwise dominate phase correlation on a pan.
    a -= ndimage.gaussian_filter(a, 3)
    b -= ndimage.gaussian_filter(b, 3)
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa, fb = np.fft.fft2(a * window), np.fft.fft2(b * window)
    cross = fa * np.conj(fb)
    cross /= np.maximum(np.abs(cross), 1e-12)
    correlation = np.abs(np.fft.ifft2(cross))
    peak = np.unravel_index(np.argmax(correlation), correlation.shape)
    shifts = [int(n if n <= size // 2 else n - size) for n, size in zip(peak, a.shape)]
    confidence = float(correlation[peak])
    if not np.isfinite(confidence):
        return (0, 0), 0.0
    return tuple(shifts), confidence


def analyze_frames(frames, exclude, region=None, pixel_threshold=12.0,
                   active_fraction=0.02, min_active_pairs=2):
    if len(frames) < 3:
        raise ValueError("need at least three sampled frames")
    height, width = frames[0].shape
    mask = measurement_mask(width, height, exclude, region)
    pair_results = []
    for first, second in zip(frames, frames[1:]):
        shift, confidence = align_translation(first, second)
        aligned = ndimage.shift(second.astype(np.float32), shift, order=0, mode="constant", cval=0)
        # Exclude the newly exposed strip and a small codec/interpolation margin.
        valid = ndimage.shift(np.ones_like(second, dtype=np.uint8), shift, order=0, mode="constant", cval=0).astype(bool)
        valid = ndimage.binary_erosion(valid, iterations=2) & mask
        if valid.sum() < width * height * 0.02:
            pair_results.append({"usable": False, "reason": "insufficient overlapping area"})
            continue
        delta = aligned - first.astype(np.float32)
        # A whole-frame exposure change is not actor movement.
        delta -= float(np.median(delta[valid]))
        absolute = np.abs(delta[valid])
        mean_delta = float(np.mean(absolute))
        changed = float(np.mean(absolute >= pixel_threshold))
        # A large cut invalidates a continuous-shot comparison instead of
        # counting it as movement.
        scene_cut = mean_delta >= 32.0 and changed >= 0.55
        # Featureless frames have no reliable translation estimate.
        extreme_shift = abs(shift[0]) > height * 0.20 or abs(shift[1]) > width * 0.20
        reliable = not extreme_shift and (confidence >= 0.025 or (mean_delta < 1.0 and changed < 0.01))
        pair_results.append({"usable": bool(reliable and not scene_cut), "scene_cut_suspected": bool(scene_cut),
                             "translation_pixels_xy": [shift[1], shift[0]], "alignment_confidence": confidence,
                             "mean_abs_delta": mean_delta, "changed_fraction": changed,
                             "active": bool(reliable and not scene_cut and changed >= active_fraction)})
    usable = [pair for pair in pair_results if pair.get("usable")]
    active = sum(pair.get("active", False) for pair in usable)
    # Require a majority of pairs to be measurable; otherwise no binary claim.
    if len(usable) < max(2, math.ceil(len(pair_results) / 2)):
        classification = "inconclusive"
    elif active >= min_active_pairs:
        classification = "localized_change_detected"
    else:
        classification = "no_localized_change_detected"
    return {"classification": classification, "sampled_frames": len(frames),
            "usable_pairs": len(usable), "active_pairs": active, "pairs": pair_results,
            "limitations": ["Only translation and median exposure change are compensated.",
                "Zoom, rotation, lighting, flicker, overlays, background deformation, bad face exclusion and tracking errors can mimic motion.",
                "A detected change does not prove natural body motion, lip sync, identity or visual quality; inspect the continuous shot."]}


def read_frames(path, start, duration, fps, max_width):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    original_width, original_height = int(stream["width"]), int(stream["height"])
    width = min(max_width, original_width)
    height = max(8, round(original_height * width / original_width))
    # One bounded continuous shot keeps both memory use and interpretation sane.
    command = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path), "-t", str(duration),
        "-an", "-vf", f"fps={fps},scale={width}:{height},format=gray", "-f", "rawvideo", "-"]
    result = subprocess.run(command, check=True, capture_output=True)
    frame_bytes = width * height
    if len(result.stdout) % frame_bytes:
        raise ValueError("partial frame returned by ffmpeg")
    frames = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height, width)
    if len(frames) < max(3, math.floor(duration * fps) - 1):
        raise ValueError("video ended before the requested analysis interval")
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--exclude", required=True, type=rectangle, help="face/mouth box: normalized x,y,width,height")
    parser.add_argument("--region", type=rectangle, help="optional body/action ROI: normalized x,y,width,height")
    parser.add_argument("--start", type=float, default=0.0, help="start of a single continuous shot in seconds")
    parser.add_argument("--duration", type=float, required=True, help="shot duration in seconds (0.5 to 30)")
    parser.add_argument("--sample-fps", type=float, default=4.0)
    parser.add_argument("--max-width", type=int, default=192)
    args = parser.parse_args()
    if (not math.isfinite(args.start) or args.start < 0 or not math.isfinite(args.duration)
            or not 0.5 <= args.duration <= 30 or not math.isfinite(args.sample_fps)
            or not 1 <= args.sample_fps <= 15 or not 64 <= args.max_width <= 512):
        parser.error("start, duration, sample-fps or max-width outside supported bounds")
    if not args.video.is_file() or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("existing video, ffmpeg and ffprobe are required")
    try:
        frames = read_frames(args.video, args.start, args.duration, args.sample_fps, args.max_width)
        report = analyze_frames(frames, args.exclude, args.region)
        report.update({"video": str(args.video.resolve()), "start_seconds": args.start,
                       "requested_duration_seconds": args.duration, "sample_fps": args.sample_fps,
                       "face_exclusion_normalized": args.exclude, "region_normalized": args.region})
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=True))
    # Inconclusive is a successful measurement with no positive motion claim.
    return 0


if __name__ == "__main__":
    sys.exit(main())
