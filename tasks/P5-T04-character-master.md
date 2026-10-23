# P5-T04 · ✋ Character master

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT → HUMAN picks | P5-T03 | Qwen-Image-2.1-Turbo | 30–60 min | ✋ yes |

**Goal:** the single portrait every shot of her is generated from. The post: "every shot of her used the first portrait as reference so she stays consistent".

## Steps
1. Load the image model. Build the prompt from the character bible in `production_prompt.md`: face, hair, coat and posture, plus the style suffix (2D hand-painted, brush texture, muted palette of ink blue, bone white, rust and deep green, soft grain, plain dark background).
2. Make a manifest `jobs/master.json` with 8 items, seeds 5001–5008, 1024×1024, txt2img. Generate each item to `stills/candidates/master_t1.png` … `master_t8.png`.
3. Contact sheet:
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --images "stills/candidates/master_t*.png" --cols 4 --out logs/sheets/P5-T04.jpg --title "character master"
   ```
4. **[HUMAN] ✋** "Pick one (1–8), or say what to change." If needed, do another round of 8 with the prompt adjusted, at most 3 rounds.
5. Copy the pick to `stills/character_master.png`. Record its seed and the final prompt in the task log.
6. Character sheet (optional): use the reference mode with the master to make one 1344×768 image showing front, three-quarter and profile views. Save it as `stills/character_sheet.png`. If it exists and the reference mode allows 2 or more images, P5-T05 uses it as a second reference.
7. Unload.

## Outputs
- `stills/character_master.png`, `stills/character_sheet.png`, contact sheet.

## Done when
- [ ] The human picked a master.
- [ ] `stills/character_master.png` exists. The sheet is optional.

## STATUS line
`P5-T04 DONE · master = t6 (seed 5006); character sheet made` (example)
