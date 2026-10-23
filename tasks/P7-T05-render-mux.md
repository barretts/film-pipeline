# P7-T05 · Render + mux

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P7-T03, P7-T04 | none (CPU) | 15–60 min | — |

**Goal:** `render/final.mp4`: 1920×1080, 24 fps, H.264 with AAC 48 kHz stereo, checked automatically.

## Steps
1. Render the full film on the CPU (16 cores) with `RENDER_CMD` from TOOLS.md, inside `render/`. Time it, send the output to `logs/tasks/P7-T05.out`, and `tail -n 5` it. Note where the output is written.
2. Mux and check:
   ```bash
   .venv/Scripts/python tools/mux_final.py --video <render.mp4> --audio mix/mix.wav --out render/final.mp4 --expect-duration <edl duration_s>
   ```
3. Make a contact sheet of `final.mp4` with 12 evenly spaced frames (`--frames 0.04,0.12,…,0.96`) and view it once.

## Outputs
- `render/final.mp4`; final contact sheet.

## Done when
- [ ] Every `mux_final.py` check passes.
- [ ] The contact sheet shows the expected shots in order.

## STATUS line
`P7-T05 DONE · final.mp4 76.4 s 1080p24; render 9 min` (example)
