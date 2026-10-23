# Phase 5: Pre-production

**Goal:** turn the brief and the real MCP logs into a locked script and shot list, a character master, and one approved still per shot.
**Who:** the agent, with three ✋ checkpoints.
**Time:** 3–5 h, including human reviews.

## The truth rule at work
- The feature list comes only from tools actually called in `logs/mcp_calls.jsonl` (P5-T01).
- The production prompt (P5-T02) gives the writer that list. The writer never invents features or numbers.
- On-screen text is referenced by `fact_ref` keys into `edit/facts.json`, never typed freehand.

## Tasks
| ID | Task | Output |
|---|---|---|
| P5-T01 | Feature list from logs | `script/features.json`, `edit/facts.json` |
| P5-T02 | Production prompt (~2,500 words) | `script/production_prompt.md` |
| P5-T03 | ✋ Script + shot list | `script/shot_list.json`, `script/lyrics.txt` |
| P5-T04 | ✋ Character master | `stills/character_master.png` (+ character sheet) |
| P5-T05 | ✋ Stills for every shot | `stills/<shot>_still.png`, contact sheets |

## Exit criteria
- `tools/validate.py shot_list script/shot_list.json` passes.
- Shot durations add up to 70–80 s, with 18–22 shots.
- Every `fact_ref` resolves in `edit/facts.json`.
- The human approved the shot list, the character and the stills.
