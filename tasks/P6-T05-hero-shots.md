# P6-T05 · Hero shots (Wan2.2-I2V-A14B, queued in the evening)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P5-T05 | Wan2.2-I2V-A14B GGUF (quant from MODELS.md) | overnight + 30 min | — |

**Goal:** the highest-quality shots (≤ 6, or the MODELS.md limit), queued together in the evening and collected the next morning.

**When to start:** check the local time with `date +%H`.
- Before ~17:00, unless the human says "go now": do P6-T07, P6-T08 and P6-T09 first. They are listed before this task in STATUS.
- At ~17:00 or later: start.

## Steps
1. **Build `jobs/hero.json`**: one item per hero shot, id `<shot>_vid_t1`. Params:
   - start frame `<ROOT>/stills/<shot>_still.png`
   - prompt: the shot's `motion_prompt` + ", 2D hand-painted animation"
   - 832×480, 81 frames, 16 fps, or MODELS.md production settings
   - seed = the shot's seed
2. **Evening.**
   1. Load A14B.
   2. Queue **all** hero items (the queue holds ≤ 32) and record each job id in the manifest.
   3. Write a handoff in `logs/tasks/P6-T05.md`: "hero queue running: ids …; collect next session".
   4. End the session. **[HUMAN]** leaves the PC on and the VRAM sampler running. Sleep is already disabled (P0-T03).
3. **Next session.**
   1. Call `get_job` for each id, at the interval set in CONTEXT §8.
   2. Download finished clips with `curl -fsS` to `video/candidates/<id>.mp4`.
   3. Mark each item `done` or `failed`.
   4. Re-queue any failure once, with seed + 1.
4. **Gate.** Same checks as P6-T04: `ffprobe` should show about 5.1 s at 16 fps, plus a contact sheet.
5. **Optional, smoother playback.** Convert to 24 fps on the CPU; it's slow, but fine:
   ```bash
   ffmpeg -hide_banner -loglevel error -nostats -y -i IN.mp4 -vf "minterpolate=fps=24:mi_mode=mci" -c:v libx264 -crf 16 -pix_fmt yuv420p OUT.mp4
   ```
   Otherwise leave the clip at 16 fps; HyperFrames holds frames.
6. **Picks.** Copy to `video/hero/<shot>_vid.mp4`, mark it `picked`, and add it to `edit/picks.json` under `shots`. Unload.

## Outputs
- `video/hero/<shot>_vid.mp4` for every hero shot
- `jobs/hero.json`
- Picks

## Done when
- [ ] Every hero shot has a picked clip.
- [ ] No hero item is left `queued` or `running`.

## If it fails
- **The queue stalled overnight:**
  1. Check `studio_status` and `cancel` any stuck job.
  2. Re-queue the remaining items with A14B Q4_K_M.
  3. If that also fails, change those shots to `motion` (5B) and record it in Decisions.

## STATUS line
`P6-T05 DONE · 5/5 hero shots overnight (41 min each)` (example)
