# P6-T04 · Motion shots (Wan2.2-TI2V-5B) + still shots

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P5-T05 | Wan2.2-TI2V-5B GGUF (still shots: CPU only) | 2–5 h (in batches) | — |

**Goal:** every `motion` shot becomes a 5-second clip animated from its approved still. Every `still` shot becomes a held clip with a slow push-in, so the edit only ever deals with video.

## Steps
1. **Build `jobs/motion.json`**: one item per motion shot, id `<shot>_vid_t1`. Params:
   - start frame `<ROOT>/stills/<shot>_still.png`
   - prompt: the shot's `motion_prompt` + ", 2D hand-painted animation, gentle motion, no camera shake"
   - 1280×704, 121 frames, 24 fps, or MODELS.md production settings
   - seed = the shot's seed
2. **Queue.** Load the 5B model and queue **≤ 8 items per session**. Record each job id:
   ```bash
   .venv/Scripts/python tools/manifest.py set jobs/motion.json <id> status=queued job_id=<job>
   ```
3. **Poll and download.** Poll as in CONTEXT §8, once per batch rather than per item. As each clip finishes:
   - download it with `curl -fsS` to `video/candidates/<id>.mp4`;
   - set it `done`, with `outputs+=` and `mcp_seq+=` (from `mcp_report.py --seq-only`).
4. **Gate each clip.**
   - `ffprobe` should show about 5.0 s, 24 fps, 1280×704.
   - Make a contact sheet of frames at 0.1, 0.5 and 0.9, 4–5 clips per sheet.
   - Reject melting, warping, off-model faces, or motion that contradicts the shot list.
   - Regenerate a rejected clip with seed + 1, up to 2 retries, then simplify the motion prompt.
5. **Pick motion clips.** Copy to `video/motion/<shot>_vid.mp4`, mark it `picked`, and add it to `edit/picks.json` under `shots` (`type`, `fps`, `width`, `height`, `duration_s`, `source`, `mcp_seq`).
6. **Unload** once all motion shots are picked.
7. **Still shots** (CPU; no MCP call needed). For each `still` shot, let F = ceil((`duration_s` + 0.5) × 24) and run:
   ```bash
   ffmpeg -hide_banner -loglevel error -nostats -y -loop 1 -i stills/<shot>_still.png \
     -vf "scale=2688:1536,zoompan=z='min(zoom+0.0006,1.06)':d=F:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1344x768:fps=24,format=yuv420p" \
     -frames:v F -c:v libx264 -crf 16 video/motion/<shot>_vid.mp4
   ```
   Replace both `F`s with the number. Add each to picks with `type` still and `source` `ffmpeg`. These shots carry no MCP facts in their pixels; their text overlays still come from facts.

## Outputs
- `video/motion/<shot>_vid.mp4` for every motion and still shot
- `jobs/motion.json`
- Picks

## Done when
- [ ] Every motion and still shot has a picked clip.
- [ ] The manifest summary shows nothing `todo`, `queued` or `running`.

## STATUS line
`P6-T04 DONE · 10 motion + 2 still shots; 3 retries; avg 13 min/clip` (example)
