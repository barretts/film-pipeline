# P3-T06 · Final mux + checks: `tools/mux_final.py`

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P3-T04, P3-T05 | none | 30–45 min | — |

**Goal:** put the mastered audio onto the silent render and verify the deliverable automatically.

## Spec
- **Usage:** `mux_final.py --video RENDER.mp4 --audio mix/mix.wav --out render/final.mp4 [--expect-duration S]`
- **Mux command:**
  ```
  ffmpeg -hide_banner -loglevel error -nostats -y -i VIDEO -i AUDIO -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 320k -ar 48000 -ac 2 -shortest -movflags +faststart OUT
  ```
  If the render isn't H.264 yuv420p, re-encode the video with `libx264 -crf 16 -preset slow -pix_fmt yuv420p` instead of copying it.
- **Checks** (ffprobe) on the output:
  - 1920×1080;
  - `r_frame_rate` 24/1;
  - video and audio durations within 0.1 s of each other, and within 0.1 s of `--expect-duration` when it's given;
  - audio AAC, 48 kHz, stereo.
- **Output:** print a JSON summary (≤ 15 lines). Exit 1 if any check fails.

## Steps
1. Write the script.
2. Pass test: mux `tests/fixtures/render_test.mp4` with a 6 s synthetic WAV:
   ```bash
   ffmpeg -hide_banner -loglevel error -nostats -y -f lavfi -i "sine=frequency=330:duration=6" -ar 48000 -ac 2 -c:a pcm_s24le tests/samples/tone6.wav
   ```
3. Fail test: use a 4 s WAV with `--expect-duration 6`.

## Outputs
- `tools/mux_final.py`.

## Done when
- [ ] The pass test passes and the fail test fails with a clear reason.

## STATUS line
`P3-T06 DONE · mux + checks pass/fail correctly` (example)
