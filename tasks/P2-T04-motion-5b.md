# P2-T04 · Motion video: Wan2.2-TI2V-5B

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T02 | Wan2.2-TI2V-5B GGUF | 30–90 min | — |

**Goal:** turn a still into a 5-second clip and measure minutes per clip.

**Read first:** P2 standard procedure; TOOLS.md (`generate_video`, `get_job`); CONTEXT §5, §8.

## Steps
1. Load the Wan2.2-TI2V-5B **GGUF** row from MODELS.md.
2. Call `generate_video` and note the job or queue id:
   - start frame `<ROOT>/tests/fixtures/scene.png` (absolute path, CONTEXT §8);
   - 1280×704, 121 frames, 24 fps, seed 2001;
   - prompt:
     > slow push-in toward the glowing machine, dust motes drifting through the lamp light, a faint flicker, 2D hand-painted animation, no camera shake
3. Wait with `get_job`: use its wait option, or poll every ≥ 60 s with `sleep 60`. Log only one status line per poll.
4. Download the result to `tests/fixtures/motion_5b.mp4`. `ffprobe` should show about 5.0 s, 24 fps, 1280×704.
5. Make a contact sheet:
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --videos tests/fixtures/motion_5b.mp4 --out logs/sheets/P2-T04.jpg
   ```
   Check that the frames differ (there is motion) and the image stays painterly.
6. Unload. Record minutes per clip and peak VRAM (use `mcp_report.py --job <id>`), and add a recipe line to TOOLS.md.

## Outputs
- `tests/fixtures/motion_5b.mp4`, `logs/sheets/P2-T04.jpg`

## Done when
- [ ] The clip has the right duration, fps and size, and shows motion.
- [ ] The measurements are recorded.

## If it fails
- **OOM:** try 960×544 with 97 frames. Record the smaller size as the new default in MODELS.md.
- **Poor motion or melting:** follow the `prompt_hint` from `studio_status` and simplify the motion.
- **Stuck for more than 45 min with no progress:** `cancel` the job, check `studio_status`, and retry once.

## STATUS line
`P2-T04 DONE · 5 s 1280×704 in 14 min, peak 15.1 GB` (example)
