# P7-T06 · ✋ Review, fixes, final report

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN reviews → AGENT fixes and reports | P7-T05 | only for fixes | 1–3 h | ✋ yes |

**Goal:** an approved final cut, and a short report that traces the making of the film to the logs, like the stats in the original post.

## Steps
1. **[HUMAN] ✋** Watch `render/final.mp4`. Reply "approve", or give a numbered fix list (shot, problem).
2. **AGENT:** apply fixes with the smallest change that solves each one:
   - re-pick an existing take;
   - regenerate one item through its manifest (respect the GPU schedule);
   - adjust timing or gain in the EDL;
   - change a builder style.

   Then re-run P7-T03 to P7-T05 as needed. Allow at most 2 fix rounds unless the human asks for more.
3. **AGENT:** write `render/REPORT.md`, ≤ 120 lines:
   - **Film:** length, resolution, fps, loudness (from `mix/loudness.json`).
   - **Models used:** each model with its variant and license, and the line **"Personal, non-commercial use only."**
   - **Compute:** per step and in total, from `mcp_report.py --json-out`; peak VRAM per model.
   - **Counts:**
     - stills generated vs picked;
     - clips per model, with retries;
     - voice-over takes generated, rejected and the reasons;
     - talking attempts.
   - **Fine-tune:** from `train/summary.json` (steps, first and final loss, export size).
   - **On-screen facts:** every overlay's text, its `fact_ref` and its evidence seq numbers.
   - **Known issues and fallbacks used.**
4. Commit. Mark P7-T06 DONE and set **Current task** in STATUS to "complete".

## Outputs
- The approved `render/final.mp4` and `render/REPORT.md`.

## Done when
- [ ] The human approved.
- [ ] REPORT.md is written, and every fact in it has an evidence seq.

## STATUS line
`P7-T06 DONE · final cut approved; report written` (example)
