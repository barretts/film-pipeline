# P4-T04 · ✋ Calibrate + pilot review

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT prepares → HUMAN approves | P4-T03 | none | 30 min | ✋ yes |

**Goal:** replace the estimates with measured numbers, fix the creative direction before the full run, and get the human's approval.

## Steps
1. **AGENT:** using the P4-T02 time table, project the full film in `logs/tasks/P4-T04.md`:

   | Step | Count (from brief/CONTEXT §5) | Minutes per item (measured) | Attempts factor | Total |
   |---|---|---|---|---|
   | Stills | ~20 shots × 2 | | | |
   | Voice-over | ~14 lines × 3 takes | | | |
   | Talking | ~4 shots | | | |
   | Motion | ~10 shots | | | |
   | Hero | ~4–6 shots | | | |
   | Music | 3 songs | | | |
   | SFX | ~12 cues × 2 | | | |
   | Fine-tune | 1 | | | |
   | Post | 1 | | | |

   Write the total, and which steps should run overnight, into STATUS › Key measurements.
2. **AGENT:** list the pipeline problems found and the fixes made, ≤ 10 lines.
3. **[HUMAN]** Watch `render/pilot_final.mp4`, then answer:
   - Look: palette, style, character on model?
   - Voice: right character? Too fast or slow?
   - Pacing and typography: title cards, captions?
   - Anything to change before the full film?
4. Record the answers in Decisions. Apply only the approved changes, to `brief.md`, CONTEXT §4–5 settings, or prompts.

## Outputs
- Projection table, measured total in STATUS, and decisions.

## Done when
- [ ] The human approved the pilot, possibly with listed changes that are now applied.

## STATUS line
`P4-T04 DONE · pilot approved; full run est. 11 h (hero overnight)` (example)
