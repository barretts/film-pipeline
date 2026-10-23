# Phase 7: Post

**Goal:** captions, edit decision list, mix, HyperFrames composition, render and mux, then review, fixes and a final report.
**Who:** the agent. The phase ends at ✋ P7-T06.
**Time:** 3–6 h, plus any fixes.

## Tasks
| ID | Task | Output |
|---|---|---|
| P7-T01 | Captions (MOSS word timings) | `captions/<id>.json` |
| P7-T02 | Edit decision list | `edit/edl.json` (validated) |
| P7-T03 | Mix | `mix/mix.wav`, `mix/loudness.json` |
| P7-T04 | Composition | `render/` HyperFrames composition |
| P7-T05 | Render + mux | `render/final.mp4` |
| P7-T06 | ✋ Review, fixes, final report | `render/REPORT.md` |

## Exit criteria
- `render/final.mp4` is 1920×1080, 24 fps, about 75 s, with 48 kHz stereo audio, and passes `mux_final.py`.
- The mix measures −14 ±1 LUFS with true peak ≤ −1.5 dBTP.
- Every on-screen fact passes `tools/facts.py check`.
- The human approved the final cut.
