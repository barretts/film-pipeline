# P2-T05 · Hero video: Wan2.2-I2V-A14B

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T03, P2-T04 | Wan2.2-I2V-A14B GGUF Q5_K_M (expert pair) | 45–120 min | — |

**Goal:** confirm that the higher-quality 14B model runs with RAM offload on this card, and measure it. Hero shots in P6 run overnight.

## Steps
1. Load the A14B **GGUF Q5_K_M expert pair** (MODELS.md). If Q5_K_M isn't offered or runs out of memory, use Q4_K_M.
2. Call `generate_video`:
   - start frame `<ROOT>/tests/fixtures/ref_scene.png` (or `ref_scene_2511.png`);
   - 832×480, 81 frames, 16 fps, seed 3001;
   - prompt:
     > she slowly turns her head toward the chalkboard, hair moving slightly, the lamp light flickers, 2D hand-painted animation
3. Wait or poll (≥ 60 s between polls). If the human has Task Manager open, note peak system RAM.
4. Download to `tests/fixtures/hero_a14b.mp4`. `ffprobe` should show about 5.1 s at 16 fps.
5. Compare quality with the 5B clip on a two-video sheet:
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --videos tests/fixtures/hero_a14b.mp4 tests/fixtures/motion_5b.mp4 --frames 0.5 --out logs/sheets/P2-T05.jpg
   ```
   In the log, note whether A14B looks clearly better (yes or no).
6. Unload. Record minutes per clip and peak VRAM in MODELS.md.

## Outputs
- `tests/fixtures/hero_a14b.mp4`, `logs/sheets/P2-T05.jpg`

## Done when
- [ ] The clip rendered and the measurements are recorded.
- [ ] The quant actually used is recorded.

## If it fails
- **Studio can't load A14B on this card at any quant:** install **ComfyUI** (MODELS.md › Fallback engines; ✋ approval for ComfyUI and any custom nodes) and use its Wan2.2 I2V GGUF workflow with block swap.
  - Record "hero shots via ComfyUI" in Decisions.
  - ComfyUI output isn't MCP-logged, so these shots must not carry on-screen facts.
- **More than 60 min per clip:** keep A14B for at most 4 hero shots, and record that limit for P5-T03.

## STATUS line
`P2-T05 DONE · A14B Q5_K_M 832×480 81f in 38 min, peak 15.6 GB, RAM 70 GB` (example)
