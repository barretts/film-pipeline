# P2-T15 · ✋ Stack review

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT prepares → HUMAN approves | P2-T01…P2-T14 | none | 20–30 min | ✋ yes |

**Goal:** the human approves the full model stack, any fallbacks used, and the talking strategy before tooling and production start.

## Steps
1. **AGENT:** make one contact sheet of the visual fixtures (≤ 12 tiles), with mid-frames for the videos. Add `tests/fixtures/talk_a2v.mp4` if it exists.
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --images tests/fixtures/portrait.png tests/fixtures/scene.png "tests/fixtures/ref_scene*.png" \
     --videos tests/fixtures/motion_5b.mp4 tests/fixtures/hero_a14b.mp4 tests/fixtures/talk_native.mp4 --frames 0.5 --out logs/sheets/P2-T15.jpg --title "stack review"
   ```
2. **AGENT:** write a summary of ≤ 20 lines into `logs/tasks/P2-T15.md`:
   - each role: model and variant, PASS or FALLBACK, peak VRAM, time per item;
   - open issues;
   - the talking strategy (A or B);
   - a rough full-film compute estimate: per-item time × the counts in CONTEXT §5, assuming ~20 shots, ~14 voice-over lines × 3 takes and 2–3 songs.
3. **[HUMAN]** Review:
   - **View:** `logs/sheets/P2-T15.jpg`.
   - **Listen:** `clone_t1.wav`, `design_t1.wav`, `music_test.wav`, `sfx_chalk_48k.wav`.
   - **Watch:** `talk_native.mp4`, and `talk_a2v.mp4` if it exists.
4. Ask: **"Approve this stack for production? (yes / change …)"**
5. Record the answer in STATUS › Decisions. If anything changed, update MODELS.md and the settings in CONTEXT §4, then repeat only the affected smoke tests.

## Outputs
- `logs/sheets/P2-T15.jpg`, the summary in the task log, and a decision in STATUS.

## Done when
- [ ] The human approved, or requested changes that are now made and re-tested.

## STATUS line
`P2-T15 DONE · stack approved; strategy A; est. 9 h compute` (example)
