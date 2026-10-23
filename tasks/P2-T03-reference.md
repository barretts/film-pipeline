# P2-T03 · Character consistency (reference/edit mode)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T02, P1-T08 | Qwen-Image-2.1-Turbo (or Qwen-Image-Edit-2511) | 20–40 min | — |

**Goal:** settle how every shot keeps the same woman: a reference or edit mode that reproduces face, hair, coat and palette from `portrait.png`.

## Steps
1. Load Qwen-Image-2.1-Turbo. Call `generate_image` in **edit/reference** mode (the mode name is in TOOLS.md):
   - reference `<ROOT>/tests/fixtures/portrait.png` (an absolute path, CONTEXT §8); size 1344×768; seed 1003;
   - save to `tests/fixtures/ref_scene.png`;
   - prompt:
     > the same woman, same face, short dark hair and rust coat, sitting at a school desk in a dim empty classroom, chalkboard behind her, 2D hand-painted, same muted palette and brush texture
2. If this model doesn't support the mode (error, or option missing):
   - unload, then load **Qwen-Image-Edit-2511**;
   - repeat step 1;
   - save to `tests/fixtures/ref_scene_2511.png`.
3. Make a contact sheet:
   ```bash
   .venv/Scripts/python tools/contact_sheet.py --images tests/fixtures/portrait.png "tests/fixtures/ref_scene*.png" --cols 3 --out logs/sheets/P2-T03.jpg --title "reference test"
   ```
   View it once. If you can't view images, ask the human to open it and answer the step 4 question.
4. Judge: same face shape, hair, coat colour and palette? Answer yes or no for each.
5. Write the working method into TOOLS.md › Capabilities: model, mode name, maximum reference images. Record seconds per image in MODELS.md › Reference shots. Unload.

## Outputs
- `tests/fixtures/ref_scene*.png`, `logs/sheets/P2-T03.jpg`
- The reference method in TOOLS.md

## Done when
- [ ] One method gives a recognizably consistent character, and it is recorded.

## If it fails
- **Neither method is consistent:** try 2 references (portrait + a second angle generated with the same description and seed).
- **Still inconsistent:** add a note for P5-T04 to train a small character LoRA (Studio supports diffusion LoRA through `start_training`). Don't do it now.

## STATUS line
`P2-T03 DONE · Qwen-Image-2.1-Turbo reference mode keeps her on-model` (example)
