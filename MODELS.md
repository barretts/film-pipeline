# MODELS: catalog ids, measurements, decisions (filled in during P1-T06 and P2)

The planned models and start settings are in CONTEXT.md §4. This file records what this PC actually ran.

| Role | Planned model | Catalog / HF id + variant | Size GB | fits_now | Peak VRAM GB | Time per item | Status | Notes / fallback used |
|---|---|---|---|---|---|---|---|---|
| Writer | Qwen3.8-27B UD-Q4_K_XL | | | | | tok/s: | ☐ | fallback UD-Q3_K_XL |
| Stills | Qwen-Image-2.1-Turbo GGUF Q4_K_M | | | | | s/image: | ☐ | |
| Reference shots | Qwen-Image-2.1-Turbo edit/ref or Qwen-Image-Edit-2511 | | | | | s/image: | ☐ | |
| Motion video | Wan2.2-TI2V-5B GGUF | | | | | min/clip: | ☐ | |
| Hero video | Wan2.2-I2V-A14B GGUF Q5_K_M | | | | | min/clip: | ☐ | fallback Q4_K_M → ComfyUI |
| Talking video | LTX-2.5 | | | | | min/clip: | ☐ | audio-driven: yes/no |
| Separation | HTDemucs | | | | | s/clip: | ☐ | fallback demucs CLI |
| Voice | Breeze-TTS-2 | | | | | s/line: | ☐ | |
| Music | YuE 2 (YuE2-3B) | | | | | min/song: | ☐ | fallback YuE2-Studio app / yue2.cpp |
| SFX + drone | MiDashengLM-Gen | | | | | s/cue: | ☐ | fallback official repo venv |
| Transcribe | MOSS-Transcribe-Diarize | | | | | s/min audio: | ☐ | |
| Fine-tune | Qwen3-0.6B LoRA → GGUF Q4_K_M | | | | | min/run: | ☐ | loss source: |
| Render | HyperFrames | n/a | n/a | n/a | CPU | s per 10 s: | ☐ | |

**Total downloaded:** _GB_ · **Free space left on model drive:** _GB_

## Production settings (override CONTEXT §5 defaults; fill in from the smoke tests)

| Role | Size | Frames / fps | Quant / variant | Limits / notes |
|---|---|---|---|---|
| Stills | 1344×768 | — | | |
| Motion video | 1280×704 | 121 / 24 | | |
| Hero video | 832×480 | 81 / 16 | Q5_K_M | max hero shots: 6 |
| Talking video | 896×512 | max frames: | | strategy A/B: |
| Voice | — | — | | reference length: |

## Fallback engines (install only when a task says so)

- **ComfyUI** (Desktop or Portable, comfy.org): Wan2.2-A14B GGUF + block swap, Wan2.2-S2V, LTX-2.5 workflows. Driven through its local HTTP API. Outputs from ComfyUI are not MCP-logged, so they may not carry on-screen facts.
- **demucs CLI** (`pip install demucs` in `.venv`): `demucs --two-stems=vocals -n htdemucs -o OUT FILE`
- **YuE2-Studio** (community Windows app) or **yue2.cpp** GGUF (`botp/YuE2-GGUF`). The official package targets Linux; WSL2 is the last resort.
- **MiDashengLM-Gen official repo** in its own venv (`venvs/midasheng/`), using `trust_remote_code`. Review the repo's code before running it.
