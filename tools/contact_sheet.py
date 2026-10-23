#!/usr/bin/env python3
"""contact_sheet.py — build ONE contact-sheet image from many images and/or video frames.

CONTEXT §9: the contact sheet is the only way visual review happens — keep it small:
<= 16 tiles, output <= 1600 px wide, JPEG quality 80.

Examples:
  contact_sheet.py --images 'stills/candidates/*.png' --out logs/sheets/stills.jpg --title stills
  contact_sheet.py --videos video/motion/s01_vid.mp4 --frames 0.1,0.5,0.9 --out logs/sheets/s01.jpg
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
from math import ceil

from PIL import Image, ImageDraw, ImageFont

MAX_TILES = 16
MAX_WIDTH = 1600

_LABEL_COLORS = ["#000000", "#ffffff"]
_BG = (24, 24, 24)
_LABEL_H = 22
_GAP = 8
_MARGIN = 8


def _font(size=18):
    for path in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow has no size kwarg
        return ImageFont.load_default()


def _run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _expand(patterns):
    """Expand a list of glob patterns (or literal paths) to files, order-stable, no dups."""
    out = []
    seen = set()
    for pat in patterns:
        matches = sorted(glob.glob(pat)) if any(c in pat for c in "*?[") else [pat]
        matched = False
        for m in matches:
            if os.path.isfile(m) and m not in seen:
                seen.add(m)
                out.append(m)
                matched = True
        if not matched:
            print(f"warning: no match for '{pat}'", file=sys.stderr)
    return out


def _video_duration(path):
    p = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ])
    try:
        return float(p.stdout.decode(errors="ignore").strip())
    except ValueError:
        return None


def _extract_frame(video, t, out_path):
    p = _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostats", "-y",
        "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-q:v", "2", out_path,
    ])
    return p.returncode == 0 and os.path.isfile(out_path)


def _tiles_for_source(kind, path, fracs, tmpdir):
    """Return list of (PIL.Image, label) — one per tile for this source."""
    base = os.path.basename(path)
    if kind == "image":
        try:
            return [(Image.open(path).convert("RGB"), base)]
        except Exception as exc:  # noqa: BLE001
            print(f"warning: unreadable image {base}: {exc}", file=sys.stderr)
            return []
    # video: pull one frame per fraction
    dur = _video_duration(path)
    if not dur:
        print(f"warning: no duration for {base}; skipped", file=sys.stderr)
        return []
    tiles = []
    for f in fracs:
        t = min(max(f * dur, 0.0), max(dur - 0.05, 0.0))
        out_jpg = os.path.join(tmpdir, f"{os.getpid()}_{len(tiles)}_{base}.jpg")
        if _extract_frame(path, t, out_jpg):
            try:
                tiles.append((Image.open(out_jpg).convert("RGB"), f"{base} {int(round(f * 100))}%"))
            except Exception as exc:  # noqa: BLE001
                print(f"warning: frame {int(f*100)}% {base} unreadable: {exc}", file=sys.stderr)
        else:
            print(f"warning: ffmpeg failed frame {int(f*100)}% of {base}", file=sys.stderr)
    return tiles


def _draw_text(draw, text, x, y, font):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        draw.text((x + dx, y + dy), text, font=font, fill=_LABEL_COLORS[0])
    draw.text((x, y), text, font=font, fill=_LABEL_COLORS[1])


def _fit_text(draw, text, width, font):
    text = text if text else ""
    while text and draw.textlength(text, font=font) > width:
        cut = max(1, int(len(text) * ((width / max(draw.textlength(text, font), 1)) * 0.92)))
        text = text[:cut]
    return text


def build_sheet(tiles, out_path, cols=4, thumb=384, title=None):
    n = len(tiles)
    cols = max(1, min(cols, n))
    rows = ceil(n / cols)
    cw = thumb
    ch = thumb + _LABEL_H
    width = 2 * _MARGIN + cols * cw + (cols - 1) * _GAP
    title_h = 44 if title else 0
    height = title_h + 2 * _MARGIN + rows * ch + (rows - 1) * _GAP

    sheet = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(sheet)
    label_font = _font(18)
    title_font = _font(30)

    y0 = _MARGIN + title_h
    for i, (img, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = _MARGIN + c * (cw + _GAP)
        y = y0 + r * (ch + _GAP)
        thumb_im = img.copy()
        thumb_im.thumbnail((cw, thumb), Image.LANCZOS)
        tx = x + (cw - thumb_im.width) // 2
        ty = y + (thumb - thumb_im.height) // 2
        sheet.paste(thumb_im, (tx, ty))
        ly = y + thumb + 2
        _draw_text(draw, _fit_text(draw, label, cw, label_font), x + 3, ly, label_font)

    if title:
        _draw_text(draw, _fit_text(draw, title, width - 2 * _MARGIN, title_font),
                   _MARGIN + 4, 8, title_font)

    if sheet.width > MAX_WIDTH:  # guarantee the width cap
        ratio = MAX_WIDTH / sheet.width
        sheet = sheet.resize((MAX_WIDTH, max(1, int(sheet.height * ratio))), Image.LANCZOS)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path, "JPEG", quality=80)
    return sheet.width, sheet.height


def main():
    ap = argparse.ArgumentParser(description="Build a contact sheet from images and/or video frames.")
    ap.add_argument("--images", nargs="+", default=[], metavar="GLOB",
                    help="image glob(s) or paths")
    ap.add_argument("--videos", nargs="+", default=[], metavar="GLOB",
                    help="video glob(s) or paths; frames pulled at --frames")
    ap.add_argument("--frames", default="0.1,0.5,0.9",
                    help="comma-separated fractions of duration (default 0.1,0.5,0.9)")
    ap.add_argument("--out", default=None, metavar="PATH",
                    help="output jpg (default logs/sheets/<timestamp>.jpg)")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--thumb", type=int, default=384, help="tile width px (default 384)")
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    out = args.out or os.path.join("logs", "sheets", time.strftime("%Y%m%d-%H%M%S") + ".jpg")
    try:
        fracs = [float(x) for x in args.frames.split(",") if x.strip() != ""]
    except ValueError:
        print("error: --frames must be comma-separated floats", file=sys.stderr)
        return 3
    if not fracs:
        print("error: --frames had no values", file=sys.stderr)
        return 3

    img_files = _expand(args.images)
    vid_files = _expand(args.videos)

    total = len(img_files) + len(vid_files) * len(fracs)
    if total == 0:
        print("error: no inputs matched", file=sys.stderr)
        return 3
    if total > MAX_TILES:
        print(f"error: {total} tiles > {MAX_TILES} limit; split the set into multiple sheets",
              file=sys.stderr)
        return 2

    tmpdir = tempfile.mkdtemp(prefix="cs_")
    try:
        tiles = []
        for f in img_files:
            tiles += _tiles_for_source("image", f, fracs, tmpdir)
        for v in vid_files:
            tiles += _tiles_for_source("video", v, fracs, tmpdir)
        if not tiles:
            print("error: no tiles could be built", file=sys.stderr)
            return 4
        w, h = build_sheet(tiles, out, cols=args.cols, thumb=args.thumb, title=args.title)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    kb = os.path.getsize(out) // 1024
    print(f"{out}\ntiles={len(tiles)} size={w}x{h} {kb}KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
