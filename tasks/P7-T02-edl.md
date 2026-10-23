# P7-T02 · Edit decision list

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P7-T01, P6-T07, P6-T08, P6-T09 | none | 45–90 min | — |

**Goal:** `edit/edl.json` is the one timeline (picture, text and sound) that both the mixer and the composition builder read.

**Read first:**
- `templates/edl.schema.json`
- `script/shot_list.json` (in sections if it's long)
- `edit/picks.json`. Every file in the EDL comes from picks; never from folder listings.

## Steps
1. **Rebuild the facts and check the picks:**
   ```bash
   .venv/Scripts/python tools/facts.py build
   .venv/Scripts/python tools/validate.py picks edit/picks.json
   ```
2. **Assemble `edit/edl.json`:** 24 fps, 1920×1080. Write it with a small one-off script, which is less error-prone than doing it by hand.

   **Video**
   - Shots go in order, each with `duration` = the shot's `duration_s` and `in: 0.2`.
   - Transitions:
     - the first shot uses `fade_from_black` 1.0 s;
     - between acts, use a 0.5 s `dissolve`;
     - everything else is a cut.
   - Each shot starts where the previous one ends: `start` = previous start + previous duration. For a dissolve, subtract the dissolve length, so the two clips overlap by exactly that much.
   - `duration_s` = the end of the last shot.

   **Audio**

   | Track | Placement |
   |---|---|
   | dialogue | **the same `start` and `in` as its talking video** (lip sync) |
   | voice | at its shot's start + `offset_s` |
   | music | `score.wav` from `music.start_s` (default 0), fades from `fade_in_s` / `fade_out_s` (defaults 2 and 3), `duck: true`, `gain_db` −6 |
   | sfx | at its shot's start + `offset_s` (default 0); `gain_db` from the cue, default −8. A cue with `shot: null` is placed at `offset_s` from film start. |
   | drone | from 0 to the end, `loop: true`, `gain_db` from the cue (default −18) |

   **Overlays** come from each shot's `on_screen` entries:
   - `kind` = the entry's `style`; copy its `fact_ref`;
   - `start` = shot start + `offset_s` (default 0.5);
   - `duration` = min(3.0, shot duration − 0.7);
   - `chalk_curve`: add `data_file` = the CSV that `facts.py get training.loss_curve` returns, plus `position: "board"`, and let it last the shot.

   **Captions:** one entry per caption file, with **the same `start` and `in` as its audio clip**. Caption times are local to the source file, and the builder shows each word at `start + (t − in)`.
3. **Validate:**
   ```bash
   .venv/Scripts/python tools/validate.py edl edit/edl.json
   ```
   Then check these:
   - `duration_s` is within ±5% of `shot_list.target_seconds`;
   - no voice-over or dialogue clips overlap;
   - no voice-over runs into a talking line;
   - no two overlays overlap.
4. **Truth check:** for every overlay, resolve its `fact_ref` with `facts.py get`, then run `facts.py check` on the resolved text. Every overlay must pass.
5. **Timeline summary:** write ≤ 30 lines into `logs/tasks/P7-T02.md` (time · shot · picture · voice · overlay).

## Outputs
- `edit/edl.json` (valid) and the timeline summary.

## Done when
- [ ] Validation is OK.
- [ ] The step 3 checks pass.
- [ ] Every overlay passes the facts check.

## STATUS line
`P7-T02 DONE · EDL 74.9 s, 20 shots, 9 overlays verified` (example)
