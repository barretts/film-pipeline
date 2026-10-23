# P2-T02 · Stills: Qwen-Image-2.1-Turbo

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T04, P1-T06 | Qwen-Image-2.1-Turbo GGUF Q4_K_M | 20–40 min | — |

**Goal:** make the first character portrait and one wide scene, and measure time per image.

**Read first:** P2 standard procedure; TOOLS.md (`generate_image`); CONTEXT §5.

## Steps
1. Load the image model (MODELS.md id; Q4_K_M).
2. Portrait, txt2img, 1024×1024, seed 1001, media as a link. Save it to `tests/fixtures/portrait.png`. Prompt:
   > 2D hand-painted portrait of a young woman with short dark hair and a rust-coloured coat, calm unreadable expression, three-quarter view, visible brush texture, muted palette of ink blue, bone white, rust and deep green, soft film grain, plain dark background, restrained A24-style mood
3. Scene, txt2img, 1344×768, seed 1002. Save it to `tests/fixtures/scene.png`. Prompt:
   > 2D hand-painted wide shot of a dark room lit by a single desk lamp, a softly glowing machine on the desk, dust in the light, muted palette of ink blue, bone white, rust and deep green, brush texture, film grain, no people
4. Check the dimensions:
   ```bash
   .venv/Scripts/python -c "from PIL import Image; [print(p, Image.open(p).size) for p in ['tests/fixtures/portrait.png','tests/fixtures/scene.png']]"
   ```
5. Unload. Record seconds per image and peak VRAM (`mcp_report.py --last 6`) in MODELS.md, and add one recipe line to TOOLS.md.

## Outputs
- `tests/fixtures/portrait.png` (1024²) and `tests/fixtures/scene.png` (1344×768)

## Done when
- [ ] Both images exist at the right sizes.
- [ ] The measurements are recorded.

## If it fails
- **The model id isn't found:** load the HF id `unsloth/Qwen-Image-2.1-Turbo-GGUF` (variant Q4_K_M).
- **OOM:** set Studio's Memory option to "Low VRAM" or turn on CPU offload, both through the `generate_image`/`load_model` params in TOOLS.md.
- **A size is rejected:** use the nearest size preset from `studio_status`, keeping both sides divisible by 32.
- **A license click-through is needed:** ✋ ask the human.

## STATUS line
`P2-T02 DONE · 1024² in 24 s, 1344×768 in 31 s, peak 11.2 GB` (example)
