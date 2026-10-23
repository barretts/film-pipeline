# P4-T03 · Pilot post

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P4-T02 | MOSS (captions), then CPU | 45–90 min | — |

**Goal:** run captions, EDL, mix, composition, render and mux for the pilot, ending in `render/pilot_final.mp4`.

## Steps
1. **Captions.** Use `pilot/edit/picks.json` as the list of files; don't glob folders.
   - For each picked voice-over and dialogue file, run MOSS with timestamps and write `pilot/captions/<id>.json`:
     ```json
     {"id": "...", "text": "...", "words": [{"w": "...", "start": 0.0, "end": 0.0}]}
     ```
     Times are local to the clip. If MOSS gives only segments, spread the words across each segment and set `"timing": "estimated"`.
   - Run `facts.py check` on each caption text.
   - Unload MOSS.
2. **Facts.** Run `facts.py build`.
3. **EDL.** Write `pilot/edit/edl.json`: 24 fps, 1920×1080, `duration_s` 14.4.

   | Track | Items |
   |---|---|
   | video | s01 start 0, s02 start 4.8, s03 start 9.6. Each has duration 4.8 and in 0.2. s01 uses `fade_from_black` 0.8 s. Between s01 and s02 use a **cut**; dissolve overlaps are tested in the full film. |
   | dialogue | s01 at **start 0 with in 0.2**, the same start and in-point as its video, so the lips stay in sync |
   | voice | v01 at s02 start + its `offset_s` |
   | music | from 0, fade in 1.5 s, fade out 2 s, `duck: true` |
   | drone | 0–14.4, looped, −18 dB |
   | sfx | each cue at its shot start + `offset_s`, at `gain_db` |
   | overlay | the s03 title at 10.4 s for 3 s |
   | captions | each caption file with the same `start` and `in` as its audio clip |

   Validate:
   ```bash
   .venv/Scripts/python tools/validate.py edl pilot/edit/edl.json
   ```
4. **Mix.**
   ```bash
   .venv/Scripts/python tools/mix.py --edl pilot/edit/edl.json --out pilot/mix/mix.wav --stems pilot/mix/stems --json-out pilot/mix/loudness.json
   ```
5. **Composition and render.**
   ```bash
   .venv/Scripts/python tools/build_composition.py --edl pilot/edit/edl.json --facts edit/facts.json --captions-dir pilot/captions --out render/
   ```
   Then run `RENDER_CMD` (TOOLS.md) inside `render/`, sending its output to `logs/tasks/P4-T03.out`, and note the render time.
6. **Mux.**
   ```bash
   .venv/Scripts/python tools/mux_final.py --video <render.mp4> --audio pilot/mix/mix.wav --out render/pilot_final.mp4 --expect-duration 14.4
   ```
7. **Contact sheet.** Make one from `pilot_final.mp4` at 0.15, 0.5 and 0.85.

## Outputs
- `render/pilot_final.mp4`
- The pilot captions, EDL and mix under `pilot/`

## Done when
- [ ] Every tool step exits 0.
- [ ] `mux_final.py` checks pass.
- [ ] The title text passed the facts check (the builder enforces it).

## If it fails
- Fix the tool that failed, add the case to its P3 test log, and re-run from that step. Don't hand-edit outputs.

## STATUS line
`P4-T03 DONE · pilot_final.mp4 14.4 s, −14.0 LUFS, checks pass` (example)
