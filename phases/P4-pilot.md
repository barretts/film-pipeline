# Phase 4: Pilot film (15 seconds)

**Goal:** run the whole chain end to end at small scale: script → stills → voice → talking/motion/hero clips → music → SFX → captions → EDL → mix → composition → render.
- Fix pipeline bugs while they're cheap.
- Replace the time estimates with real numbers.

**Who:** the agent. The phase ends at ✋ P4-T04.
**Time:** 3–5 h.

## Pilot spec
- **3 shots:**
  - s01 talking, 4.8 s, one spoken line;
  - s02 motion, 4.8 s, one voice-over line;
  - s03 hero, 4.8 s, one title card from the logs.
- **Sound:** 15–20 s of music, 2 SFX cues and a drone bed.
- **Files:** everything for the pilot lives under `pilot/` (script, stills, video, audio, captions, edit, mix), so nothing mixes with film files. Manifests are `jobs/pilot_*.json`. The output is `render/pilot_final.mp4`.

## Tasks
| ID | Task |
|---|---|
| P4-T01 | Pilot script and shot list (writer model) |
| P4-T02 | Pilot assets (stills, voice, three clips, music, SFX) |
| P4-T03 | Pilot post (captions, EDL, mix, composition, render, mux) |
| P4-T04 | ✋ Calibrate the time model; human reviews `render/pilot_final.mp4` |

## Exit criteria
- `render/pilot_final.mp4` plays and passes the `mux_final.py` checks.
- The human approved the look, voice and pacing, or the changes are recorded in Decisions.
- STATUS.md › Key measurements holds a full-run time estimate built from the measured per-item times.
