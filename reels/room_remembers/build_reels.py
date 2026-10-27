"""Build three self-contained, editable HyperFrames reels from local media."""
import argparse
from array import array
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parent.parent
LEAD = 0.8


def command(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                             "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def speech_correlation(left, right):
    samples = []
    for path in (left, right):
        result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                                 "-ar", "16000", "-f", "s16le", "-"], check=True, capture_output=True)
        values = array("h")
        values.frombytes(result.stdout)
        samples.append(values)
    n = min(map(len, samples))
    if n < 100:
        raise ValueError("speech audio is empty")
    a, b = (v[:n] for v in samples)
    mean_a, mean_b = sum(a) / n, sum(b) / n
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    denominator = math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
    return numerator / denominator if denominator else 0.0


def caption_scene(spec, total, profile):
    groups = []
    for index, (start, end, words) in enumerate(spec["captions"]):
        start, end = start + LEAD, end + LEAD
        groups.append(f'<div id="caption-{index}" class="clip caption" data-start="{start:.3f}" '
                      f'data-duration="{end-start:.3f}" data-track-index="0">'
                      f'<span class="caption-text">{html.escape(words)}</span></div>')
    top, left, width, font, line_height = (1224, 146, 788, 48, 1.32) if profile == "standard" else (1090, 125, 830, 72, 1.18)
    return f'''<template>
<style>
  #root {{ position:absolute; inset:0; pointer-events:none; }}
  .caption {{ position:absolute; top:{top}px; left:{left}px; width:{width}px; text-align:center; text-wrap:balance; z-index:20; }}
  .caption-text {{ display:inline; padding:9px 15px 11px; box-decoration-break:clone;
    background:rgba(10,18,22,.88); color:#fffaf0; font:600 {font}px/{line_height} "Inter",sans-serif;
    letter-spacing:.005em; }}
</style>
<div id="root" data-composition-id="captions" data-width="1080" data-height="1920">
{chr(10).join(groups)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const captionsTimeline = gsap.timeline({{ paused:true }});
captionsTimeline.to({{}}, {{ duration:{total:.3f} }}, 0);
window.__timelines["captions"] = captionsTimeline;
</script>
</template>'''


def index_html(spec, duration_s, total, variant, profile):
    cut_start = LEAD + spec["cut"][0]
    cut_duration = spec["cut"][1] - spec["cut"][0]
    title = html.escape(spec["title"])
    subtitle = html.escape(spec["subtitle"])
    themes = {
        "01": {"accent": "#ffd3e4", "font": '"Archivo Black",sans-serif', "size": 74},
        "02": {"accent": "#ffe2ad", "font": '"EB Garamond",serif', "size": 84},
        "03": {"accent": "#b8f1f5", "font": '"Montserrat",sans-serif', "size": 76},
    }
    theme = themes[spec["id"]] if variant == "styled" else {"accent": "#f4d8bc", "font": '"EB Garamond",serif', "size": 84}
    label_size = 48 if profile == "readable_labels" else 35
    opener = (f'<img id="opener" class="clip" data-start="0" data-duration="2.200" '
              f'data-track-index="3" src="assets/opener.png" alt="">' if spec["id"] != "01" else "")
    return f'''<!doctype html>
<html lang="en" data-resolution="portrait">
<head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920">
<script src="assets/vendor/gsap.min.js"></script>
<style>
* {{ box-sizing:border-box; }}
html,body {{ margin:0; width:1080px; height:1920px; overflow:hidden; background:#101a20; }}
#root {{ position:relative; width:1080px; height:1920px; overflow:hidden; background:#101a20; }}
.stage {{ position:absolute; left:0; top:0; width:1080px; height:1920px; overflow:hidden; }}
.stage img,.stage video {{ position:absolute; inset:0; width:1080px; height:1920px; object-fit:cover; }}
#poster {{ z-index:1; }} #talk {{ z-index:2; }} #broll,#opener {{ z-index:3; }}
#opener {{ transform:scale({spec.get('opener_scale', 1)}); }}
.eyebrow {{ position:absolute; top:205px; left:105px; width:870px; text-align:center;
  color:{theme['accent']}; font:600 {label_size}px/1.2 "Space Mono",monospace; letter-spacing:.08em; }}
.eyebrow span {{ padding:5px 9px; background:rgba(10,18,22,.88); white-space:nowrap; }}
.hook {{ position:absolute; top:300px; left:105px; width:870px; text-align:center;
  color:#faf3e5; font:700 {theme['size']}px/.99 {theme['font']}; letter-spacing:.015em; }}
.hook span {{ padding:6px 14px; background:rgba(10,18,22,.88); box-decoration-break:clone; }}
.line {{ position:absolute; top:1466px; left:410px; width:260px; height:2px; background:#b69379; }}
</style></head>
<body><div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}"
 data-width="1080" data-height="1920">
  <div class="stage" data-layout-allow-overlap data-layout-allow-overflow>
    <img id="poster" class="clip" data-start="0" data-duration="{total:.3f}" data-track-index="0" src="assets/poster.png" alt="">
    <video id="talk" class="clip" data-start="{LEAD:.3f}" data-duration="{duration_s:.3f}" data-track-index="1" src="assets/talking.mp4" muted playsinline></video>
    <img id="broll" class="clip" data-start="{cut_start:.3f}" data-duration="{cut_duration:.3f}" data-track-index="2" src="assets/scene.png" alt="">
    {opener}
  </div>
  <div id="eyebrow" class="clip eyebrow" data-start="0" data-duration="{total:.3f}" data-track-index="3"><span>{subtitle}</span></div>
  <div id="hook" class="clip hook" data-start="0" data-duration="2.200" data-track-index="4"><span>{title}</span></div>
  <div id="line" class="clip line" data-start="0" data-duration="{total:.3f}" data-track-index="3"></div>
  <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html"
    data-start="0" data-duration="{total:.3f}" data-track-index="5" data-track-kind="captions"
    data-width="1080" data-height="1920"></div>
  <audio id="speech" class="clip" data-start="{LEAD:.3f}" data-duration="{duration_s:.3f}" data-track-index="6" data-volume="1" src="assets/voice.wav"></audio>
  <audio id="music" class="clip" data-start="0" data-duration="{total:.3f}" data-track-index="7" data-volume="0.12" data-fade-in="0.6" data-fade-out="0.8" src="assets/music.wav"></audio>
  <audio id="accent" class="clip" data-start="{spec['accent_start']:.3f}" data-duration="{spec['accent_duration']:.3f}" data-track-index="8" data-volume="0.20" src="assets/accent.wav"></audio>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const timeline = gsap.timeline({{ paused:true }});
timeline.fromTo(".stage", {{scale:1}}, {{scale:1.045,duration:{total:.3f},ease:"none"}}, 0);
timeline.fromTo("#broll", {{opacity:0}}, {{opacity:1,duration:.16,ease:"power1.out"}}, {cut_start:.3f});
timeline.to("#broll", {{opacity:0,duration:.18,ease:"power1.in"}}, {cut_start + cut_duration - .18:.3f});
timeline.fromTo("#hook span", {{opacity:1}}, {{opacity:0,duration:.25,ease:"power1.in"}}, 1.95);
timeline.to({{}}, {{duration:{total:.3f}}}, 0);
window.__timelines["main"] = timeline;
</script></body></html>'''


def build(spec, variant, destination, overwrite, profile):
    ident = spec["id"]
    def source(key, fallback):
        return (ROOT / spec.get(key, fallback)).resolve()
    talking = source("talking", ROOT / "video" / "reels" / ("styled" if variant == "styled" else "") / f"{ident}.mp4")
    voice = source("voice", ROOT / "audio" / "reels" / f"{ident}-paced.wav")
    broll = source("broll", ROOT / "stills" / "reels" / ("styled" if variant == "styled" else "") / f"{ident}.png")
    opener = source("opener", broll)
    portrait = source("portrait", (ROOT / "stills" / "reels" / "characters" / f"{ident}.png" if variant == "styled"
                                  else ROOT / "stills" / "lipsync" / "character.png"))
    music = source("music", ROOT / "audio" / "reels" / "sfx" / "ambient.wav")
    accent = source("accent_path", ROOT / "audio" / "reels" / "sfx" / spec["accent"])
    sources = [talking, voice, broll, opener, portrait, music, accent, PROJECT / "assets" / "vendor" / "gsap.min.js"]
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Required local media missing: {source}")
    spoken, video = duration(voice), duration(talking)
    if abs(spoken - video) > .15:
        raise ValueError(f"{ident}: talking video {video:.3f}s does not match speech {spoken:.3f}s")
    correlation = speech_correlation(voice, talking)
    if correlation < .90:
        raise ValueError(f"{ident}: talking video audio does not match speech (correlation {correlation:.3f})")
    if spec["captions"][-1][1] > spoken + .05 or spec["cut"][1] > spoken:
        raise ValueError(f"{ident}: caption or visual timing extends past the narration")
    total = (max(12.0, LEAD + spoken + 1.5) if profile == "standard" or ident == "01"
             else LEAD + spoken + 1.35)
    episode = destination / ident
    if (episode / "index.html").exists() and not overwrite:
        raise FileExistsError(f"{episode} already exists; choose a new --out-dir or pass --overwrite")
    assets = episode / "assets"
    (assets / "vendor").mkdir(parents=True, exist_ok=True)
    (episode / "compositions").mkdir(parents=True, exist_ok=True)
    for src, dst in [(voice, assets / "voice.wav"), (music, assets / "music.wav"),
                     (accent, assets / "accent.wav"), (broll, assets / "scene.png"), (opener, assets / "opener.png"), (portrait, assets / "poster.png"),
                     (PROJECT / "assets" / "vendor" / "gsap.min.js", assets / "vendor" / "gsap.min.js")]:
        shutil.copyfile(src, dst)
    # Short GOPs make frame-accurate browser seeking reliable; retain the source separately.
    command(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(talking), "-an", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "17", "-g", "25", "-keyint_min", "25", "-sc_threshold", "0",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(assets / "talking.mp4")])
    (episode / "index.html").write_text(index_html(spec, spoken, total, variant, profile), encoding="utf-8")
    (episode / "compositions" / "captions.html").write_text(caption_scene(spec, total, profile), encoding="utf-8")
    shutil.copyfile(PROJECT / "hyperframes.json", episode / "hyperframes.json")
    (episode / "meta.json").write_text(json.dumps({"title": spec["subtitle"]}, indent=2), encoding="utf-8")
    print(f"Built {ident}: {total:.3f}s, voice {spoken:.3f}s, audio match {correlation:.4f}, project {episode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", choices=["01", "02", "03"], action="append")
    parser.add_argument("--variant", choices=["original", "styled"], default="original")
    parser.add_argument("--spec", type=Path, default=PROJECT / "reels.json", help="JSON list of reel specs")
    parser.add_argument("--out-dir", type=Path, help="Separate project directory for another round")
    parser.add_argument("--profile", choices=["standard", "large_captions", "readable_labels"], default="standard")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing generated episode files")
    args = parser.parse_args()
    specs = json.loads(args.spec.read_text(encoding="utf-8"))
    destination = (args.out_dir or PROJECT / ("episodes_styled" if args.variant == "styled" else "episodes")).resolve()
    if not destination.is_relative_to(PROJECT):
        parser.error("--out-dir must be inside the reel project")
    try:
        for spec in specs:
            if not args.episode or spec["id"] in args.episode:
                build(spec, args.variant, destination, args.overwrite, args.profile)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"build error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
