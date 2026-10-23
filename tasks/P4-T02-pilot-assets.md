# P4-T02 · Pilot assets

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P4-T01 | each model in turn | 2–3 h | — |

**Goal:** make every pilot asset with the production methods (manifests, QA gates, picks), and measure the real time per item.

**Read first:**
- P6 phase file (batch rules)
- MODELS.md (production settings)
- TOOLS.md
- STATUS › Decisions (talking strategy)

## Steps
Batch by model and unload between groups. Use one manifest per model, `jobs/pilot_<group>.json` (via `tools/manifest.py`). Media inputs take absolute paths (CONTEXT §8).

1. **Stills** (image model):
   - 3 shots × 2 takes, using the P2-T03 reference method with `tests/fixtures/portrait.png` (shots where `has_character` is true), at 1344×768.
   - Make a contact sheet and pick one per shot: `pilot/stills/s0N_still.png`.
2. **Voice** (Breeze-TTS-2 + MOSS):
   - Reference: `tests/fixtures/voice_ref_test.wav` and `.txt`.
   - Make 3 takes of v01. For each take, transcribe it with MOSS, then:
     ```bash
     .venv/Scripts/python tools/qa_take.py --audio TAKE --expected "LINE" --transcript TAKE.transcript.json --ref tests/fixtures/voice_ref_test.wav
     ```
   - Copy the best PASS to `pilot/audio/vo/v01_vo.wav` (48 kHz).
   - **Strategy A only:** also make and gate takes of s01's talking line (`s01_dlg_tN`), and pick one to `pilot/audio/dialogue/s01_dlg.wav`.
3. **Talking** (LTX-2.5), s01:
   - **Strategy A:** drive it with the picked `s01_dlg.wav`.
   - **Strategy B:**
     1. Generate the takes, using the prompted line plus the voice description.
     2. **Unload LTX.**
     3. Gate every take as a batch: extract the audio, run HTDemucs, then MOSS, then `qa_take.py` against the reference.
     4. Reload LTX only for retries, up to 4 attempts in total.

   Save `pilot/video/s01_talk.mp4`. For strategy B, also save `pilot/audio/dialogue/s01_dlg.wav`.
4. **Motion** (Wan2.2-5B): s02 → `pilot/video/s02_vid.mp4`.
5. **Hero** (A14B): s03 → `pilot/video/s03_vid.mp4`.
6. **Music** (YuE 2): the pilot style and lyrics, about 20 s → `pilot/audio/music/score.wav`.
7. **SFX** (MiDashengLM-Gen): 2 cues plus one 15–20 s drone. Resample to 48 kHz and normalize as in P6-T08 → `pilot/audio/sfx/x0N_sfx.wav`.
8. **Time table.** After each group, run `mcp_report.py --last 20` and add rows to a per-item time table in `logs/tasks/P4-T02.md` with columns: asset, model, attempts, minutes, peak VRAM.
9. **Picks file.** Write `pilot/edit/picks.json` in the picks format (`templates/picks.schema.json`), then:
   ```bash
   .venv/Scripts/python tools/validate.py picks pilot/edit/picks.json
   ```

## Outputs
- Every pilot asset above
- `jobs/pilot_*.json`
- `pilot/edit/picks.json`
- The time table

## Done when
- [ ] Every asset exists and passed its gate: voice-over and dialogue PASS, clips checked on contact sheets.
- [ ] The picks file validates.
- [ ] The time table is complete.

## If it fails
- Use the model's fallback from MODELS.md, and note what failed in the time table. Finding these problems is what the pilot is for.

## STATUS line
`P4-T02 DONE · all pilot assets; talking took 3 attempts; table logged` (example)
