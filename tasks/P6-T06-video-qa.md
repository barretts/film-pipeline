# P6-T06 · Video QA + reshoots

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P6-T03, P6-T04, P6-T05 | only for reshoots | 30 min + reshoots | — |

**Goal:** check every picked clip in film order, reshoot the weak ones, and lock `edit/picks.json` for the video track.

## Steps
1. Build contact sheets of the picked clips **in shot order**, with each clip's mid-frame, ≤ 16 tiles per sheet. Make a second set of last frame plus next shot's first frame, to check continuity across cuts.
2. Check each clip:
   - is she on-model (face, hair, coat)?
   - any warped hands or face?
   - does it keep the palette?
   - does the motion match the shot list?
   - any garbled text or artifacts?
   - talking shots: do the lips look plausible?
3. Write a reshoot list in the task log, at most 25% of shots, with the reason for each.
4. Reshoot through the manifest for that shot's model, with a new seed or a simpler prompt. Keep the GPU schedule: batch reshoots by model.
5. Finalize `edit/picks.json`. Every shot needs:
   - `file`, `type`, `duration_s` (from `ffprobe`), `fps`;
   - the source manifest item id and `mcp_seq`.
6. Validate the picks:
   ```bash
   .venv/Scripts/python tools/validate.py picks edit/picks.json
   ```
   This checks that the files exist and that every shot has an entry. Audio entries may still be incomplete here.

## Outputs
- Locked video section of `edit/picks.json`; contact sheets in `logs/sheets/`.

## Done when
- [ ] Every shot has a checked pick.
- [ ] The reshoot list is resolved.

## STATUS line
`P6-T06 DONE · 20/20 shots locked; 3 reshot` (example)
