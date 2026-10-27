"""Build a separate editable HyperFrames reel from verified moving speech footage."""
import argparse
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import motion_qa

# Reuse the established audio comparison; the moving video must contain this
# narration at time zero. Its audio is then muted in the composition.
sys.path.insert(0, str(ROOT / "reels" / "room_remembers"))
from build_reels import speech_correlation, duration

EXCLUSIONS = {"01": [0.18, 0.02, 0.65, 0.36],
              "02": [0.25, 0.08, 0.45, 0.27],
              "03": [0.22, 0.10, 0.56, 0.28]}


def validate(video, voice, face_box):
    if not video.is_file() or not voice.is_file():
        raise ValueError("video and voice must be existing local files")
    spoken = duration(voice)
    if not math.isfinite(spoken) or spoken < 2:
        raise ValueError("narration must be at least two seconds")
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration", "-of", "json", str(video)],
        check=True, capture_output=True, text=True)
    stream = json.loads(probe.stdout)["streams"][0]
    # WAN's 704x1280 portrait is close to 9:16; object-fit:cover removes
    # a small amount at top and bottom when filling the final 1080x1920 frame.
    if abs(int(stream["width"]) / int(stream["height"]) - 9 / 16) > .025:
        raise ValueError("video must be approximately portrait 9:16")
    if float(stream.get("duration") or 0) + 0.005 < spoken:
        raise ValueError("video is shorter than narration")
    # Check decoded length, not just correlation over whichever samples happen
    # to exist: a matching first second must not validate a truncated soundtrack.
    audio = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:a:0",
                            "-t", str(spoken), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                           check=True, capture_output=True).stdout
    if len(audio) / 32000 + .02 < spoken:
        raise ValueError("video audio is shorter than narration")
    correlation = speech_correlation(voice, video)
    if correlation < .90:
        raise ValueError(f"video audio does not match narration (correlation {correlation:.3f})")
    # Decode all of the input span: a valid container duration alone does not
    # prove the video or its audio can actually be decoded.
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-t", str(spoken),
                    "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
                   check=True, capture_output=True)
    # Cover the complete narration in overlapping 2-second windows. A positive
    # result indicates pixel changes outside a face box, not good animation.
    starts = [i * 2.0 for i in range(int(spoken // 2))]
    if not starts or starts[-1] + 2 < spoken - .001:
        starts.append(spoken - 2)
    reports = []
    for start in starts:
        frames = motion_qa.read_frames(video, start, 2.0, 4.0, 192)
        report = motion_qa.analyze_frames(frames, face_box)
        if report["classification"] != "localized_change_detected":
            raise ValueError(f"insufficient or inconclusive non-face motion at {start:.2f}–{start+2:.2f}s: {report['classification']}")
        reports.append({"start": start, "duration": 2.0, **report})
    return spoken, correlation, reports


def caption_scene(spec, total):
    groups = []
    for index, (start, end, words) in enumerate(spec["captions"]):
        if start < 0 or end <= start or end > total + .005:
            raise ValueError("caption timing exceeds narration")
        groups.append(f'<div id="caption-{index}" class="clip caption" data-start="{start:.3f}" '
                      f'data-duration="{end-start:.3f}" data-track-index="0"><span>{html.escape(words)}</span></div>')
    return f'''<template>
<style>#root{{position:absolute;inset:0;pointer-events:none}} .caption{{position:absolute;top:1190px;left:100px;width:880px;text-align:center;color:white;font:600 64px/1.2 sans-serif;text-wrap:balance}} .caption span{{padding:8px 14px;background:rgba(10,18,22,.9);box-decoration-break:clone}}</style>
<div id="root" data-composition-id="captions" data-width="1080" data-height="1920">{''.join(groups)}</div>
<script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});tl.to({{}},{{duration:{total:.3f}}},0);window.__timelines["captions"]=tl;</script>
</template>'''


def index_html(total):
    return f'''<!doctype html><html lang="en" data-resolution="portrait"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920"><script src="assets/vendor/gsap.min.js"></script><style>
*{{box-sizing:border-box}}html,body,#root{{margin:0;width:1080px;height:1920px;overflow:hidden;background:#101a20}}#root{{position:relative}}#talk{{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover}}
</style></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="1080" data-height="1920">
<video id="talk" class="clip" data-start="0" data-duration="{total:.3f}" data-track-index="0" src="assets/talking.mp4" muted playsinline></video>
<div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html" data-start="0" data-duration="{total:.3f}" data-track-index="1" data-track-kind="captions" data-width="1080" data-height="1920"></div>
<audio id="speech" class="clip" data-start="0" data-duration="{total:.3f}" data-track-index="2" data-volume="1" src="assets/voice.wav"></audio>
<audio id="music" class="clip" data-start="0" data-duration="{total:.3f}" data-track-index="3" data-volume="0.12" data-fade-in="0.6" data-fade-out="0.8" src="assets/music.wav"></audio>
</div><script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});tl.to({{}},{{duration:{total:.3f}}},0);window.__timelines["main"]=tl;</script></body></html>'''


def build(spec, video, voice, music, destination, face_box):
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    if not music.is_file():
        raise ValueError("music file is missing")
    spoken, correlation, reports = validate(video, voice, face_box)
    total = spoken
    if duration(music) + .005 < total:
        raise ValueError("music is shorter than the narration")
    caption_html = caption_scene(spec, spoken)
    destination.mkdir(parents=True)
    assets = destination / "assets"
    (assets / "vendor").mkdir(parents=True)
    (destination / "compositions").mkdir()
    for source, target in ((video, assets / "talking.mp4"), (voice, assets / "voice.wav"),
                           (music, assets / "music.wav"),
                           (ROOT / "reels/room_remembers/assets/vendor/gsap.min.js", assets / "vendor/gsap.min.js")):
        shutil.copyfile(source, target)
    (destination / "index.html").write_text(index_html(total), encoding="utf-8")
    (destination / "compositions/captions.html").write_text(caption_html, encoding="utf-8")
    (destination / "meta.json").write_text(json.dumps({"title": spec["subtitle"]}, indent=2), encoding="utf-8")
    shutil.copyfile(ROOT / "reels/room_remembers/package.json", destination / "package.json")
    shutil.copyfile(ROOT / "reels/room_remembers/hyperframes.json", destination / "hyperframes.json")
    (destination / "input-review.json").write_text(json.dumps({"voice_seconds": spoken,
        "timeline_seconds": total, "audio_correlation": correlation, "face_exclusion": face_box,
        "motion_windows": reports, "note": "Pixel changes do not prove actor movement, lip sync, or visual quality; inspect footage."}, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", choices=sorted(EXCLUSIONS), required=True)
    parser.add_argument("--video", type=Path, required=True, help="narration-length moving lip-synced video with matching audio")
    parser.add_argument("--out", type=Path, required=True, help="new project directory; never overwritten")
    parser.add_argument("--face-box", type=motion_qa.rectangle, help="face exclusion x,y,width,height normalized 0..1; must cover face throughout")
    args = parser.parse_args()
    spec = next(x for x in json.loads((ROOT / "reels/room_remembers/reels-round-04.json").read_text(encoding="utf-8")) if x["id"] == args.id)
    try:
        build(spec, args.video, ROOT / "audio/reels" / f"{args.id}-paced.wav",
              ROOT / "audio/reels/sfx/ambient.wav", args.out, args.face_box or EXCLUSIONS[args.id])
    except (ValueError, OSError, subprocess.SubprocessError, KeyError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Created editable project: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
