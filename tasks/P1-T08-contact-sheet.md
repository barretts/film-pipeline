# P1-T08 · Contact-sheet tool

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P0-T04 | none | 30–45 min | — |

**Goal:** review many images and video frames with **one** small image. This is the only way visual review happens (CONTEXT §9).

## Spec: `tools/contact_sheet.py`
- **Inputs:**
  - `--images GLOB [GLOB…]`;
  - `--videos GLOB [GLOB…]`, which pulls frames at `--frames 0.1,0.5,0.9` of the duration using ffprobe and ffmpeg;
  - `--out PATH` (default `logs/sheets/<timestamp>.jpg`);
  - `--cols 4`, `--thumb 384` (tile width in px), `--title TEXT`.
- **Layout:**
  - tiles keep aspect ratio and carry a small label (filename, plus frame % for videos);
  - the optional title goes on a top bar;
  - output is ≤ 1600 px wide, JPEG quality 80.
- **Limit:** ≤ 16 tiles. If there are more, exit 2 and tell the caller to split the set.
- **Output:** prints the path, tile count and size in KB.
- **Implementation:** PIL plus subprocess calls to ffmpeg/ffprobe. Temp frames go in a temp folder that is deleted afterwards.

## Steps
1. Write the script to the spec.
2. Make test inputs:
   ```bash
   .venv/Scripts/python -c "from PIL import Image; Image.new('RGB',(1344,768),(40,60,90)).save('tests/samples/a.png'); Image.new('RGB',(1024,1024),(140,70,40)).save('tests/samples/b.png')"
   ffmpeg -hide_banner -loglevel error -nostats -y -f lavfi -i testsrc=duration=3:size=640x360:rate=24 -pix_fmt yuv420p tests/samples/t.mp4
   ```
3. Run it:
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --images "tests/samples/*.png" --videos tests/samples/t.mp4 --out logs/sheets/test.jpg --title test
   ```
   Expect 5 tiles.
4. Check the output is ≤ 1600 px wide. If you can view images, view it once to confirm the labels are readable.
5. Check the 16-tile limit with 17 inputs. It should exit with code 2.

## Outputs
- `tools/contact_sheet.py`; `logs/sheets/test.jpg`.

## Done when
- [ ] The 5-tile sheet was made and is ≤ 1600 px wide.
- [ ] The 17-input run exits with code 2.

## If it fails
- **No font is available for labels:** use `ImageFont.load_default()`.
- **Frames come out black:** seek with `-ss` before `-i` and add `-frames:v 1`.

## STATUS line
`P1-T08 DONE · contact sheets work (images + video frames)` (example)
