# Phase 6: Production

**Goal:** generate every asset in the shot list:
- the voice reference, voice-over takes and talking shots;
- motion shots and hero shots;
- music, SFX and drone;
- the Qwen3-0.6B fine-tune and its loss curve.

Every asset passes its QA gate.

**Who:** the agent. ✋ P6-T01 is the voice approval.
**Time:** 8–14 h of compute, including one overnight run (P6-T05).

## GPU schedule (batch by model; never interleave)
1. **Breeze-TTS-2 + MOSS:** P6-T01 voice reference, then P6-T02 voice-over takes.
2. **LTX-2.5:** P6-T03 talking shots.
3. **Wan2.2-TI2V-5B:** P6-T04 motion shots. Still shots in the same task use CPU only.
4. **Wan2.2-I2V-A14B:** P6-T05 hero shots. Queue them at the end of a day and let them run overnight.
5. **YuE 2:** P6-T07 music.
6. **MiDashengLM-Gen:** P6-T08 SFX and drone.
7. **Qwen3-0.6B training + export:** P6-T09.
8. **Reshoots:** P6-T06, re-running whichever of the models above it needs.

STATUS lists P6-T07, P6-T08 and P6-T09 before P6-T05. They fill the day, and P6-T05 starts in the evening (its task file checks the time).

## Batch rules
- Each batch lives in a manifest, `jobs/<name>.json`. Create and update it with `tools/manifest.py`.
- Each manifest covers one model. Update the manifest after every item.
- Every item goes through its QA gate before it's marked `done`. The pick is marked `picked`, copied to its pick filename (§7), and recorded in `edit/picks.json`, which follows `templates/picks.schema.json` and has the sections `shots`, `vo`, `dialogue`, `music` and `sfx`.
- **Batch limits per session:** ≤ 8 image/video items, or ≤ 24 audio takes.
- A manifest item records `mcp_seq` (the log line numbers) for traceability.

## Tasks
| ID | Task | Manifest |
|---|---|---|
| P6-T01 | ✋ Voice reference | — |
| P6-T02 | Voice-over takes + QA | jobs/vo.json |
| P6-T03 | Talking shots | jobs/talking.json |
| P6-T04 | Motion + still shots | jobs/motion.json |
| P6-T05 | Hero shots (overnight) | jobs/hero.json |
| P6-T06 | Video QA + reshoots | edit/picks.json |
| P6-T07 | Music | jobs/music.json |
| P6-T08 | SFX + drone | jobs/sfx.json |
| P6-T09 | Fine-tune + loss curve | — (train/) |

## Exit criteria
- `edit/picks.json` names one approved file for every shot, voice-over line, talking line, sound cue and the score, and `validate.py picks edit/picks.json` is OK.
- `train/loss.csv` and `train/summary.json` exist, and their values trace to MCP log seq numbers.
- No manifest still has items in `todo`, `queued` or `running`.
