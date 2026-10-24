# TOOLS: Unsloth Studio MCP reference (filled in by P1-T05)

Keep this file under ~2,500 tokens: one line per tool, key parameters only. Never paste full schemas.

**Server name in Codex:** _pending P1-T02_ (tools appear as `mcp__<server>__<tool>`)
**Studio URL:** http://127.0.0.1:8888 (HTTP 200 verified 2026-10-23) · **Studio server version:** 2026.10.8 (`/openapi.json`) · **`unsloth doctor --mcp` verdict:** _pending P1-T02_

## Tools

Rows were pre-filled from the Unsloth release notes. Confirm each one, fix parameter names, and add any tools that are missing.

| Tool | Confirmed? | Use | Key params (as named by the server) | Returns / notes |
|---|---|---|---|---|
| studio_status | ☐ | GPU memory, loaded model slots, generation in progress, video capabilities | — | video: prompt_hint, supports_last_frame, references, size_presets |
| list_models | ☐ | downloaded models, or the downloadable catalog | source (local/catalog), workflow filter | catalog rows: size_bytes, low_vram, fits_now |
| load_model | ☐ | load llm/image/video/stt/tts/audio model | model id, variant/quant, kind, context? preview? | may report models it unloads |
| unload_model | ☐ | free the GPU | model/slot | |
| chat | ☐ | text generation with the loaded LLM | messages, reasoning effort?, temperature… | |
| generate_image | ☐ | txt2img, img2img, inpaint, upscale, edit/reference/outpaint | prompt, size, seed, steps, reference images, return_media | images inline by default, so always ask for a link |
| generate_audio | ☐ | clone, speak, edit, convert, music, separate | mode, model, text, reference audio + text, instruction, return_media | default return is a link |
| transcribe | ☐ | ASR with timestamps/speakers | audio, model | |
| generate_video | ☐ | start a video job (queued if busy) | prompt, start frame, size, frames, fps, seed, audio? | job/queue id; queue ≤ 32 |
| get_job | ☐ | progress/result for video, recipe, export jobs | id, wait/follow? | |
| cancel | ☐ | cancel training/export/recipe/image/video/chat/download | id | |
| start_training | ☐ | LLM or diffusion LoRA training | base model, dataset, hyperparams, validate_only | run id |
| list_training_runs | ☐ | runs and checkpoints | — | loss history? (P2-T13) |
| export_model | ☐ | gguf / merged / lora / base | run/checkpoint, format, quant | job id |
| datasets | ☐ | list, check_format, download, status (upload?) | | |
| run_recipe | ☐ | Data Recipes: validate, preview, full | | |
| chat-related: embed, system_one | ☐ | not needed for the film | | |

**MCP prompts (slash commands):** make_short_film(idea, length_seconds) ☐ · build_dataset_and_train(goal, base_model) ☐

## Capabilities discovered (fill in during P2)

- generate_image reference/edit with Qwen-Image-2.1-Turbo: _yes/no; which mode name_
- generate_video start frame for Wan2.2-5B / A14B / LTX-2.5: _…_
- LTX-2.5 audio input (audio-driven lip sync): _yes/no; param name_ (P2-T10)
- get_job wait/follow option: _yes/no; max wait_
- Where the training loss history comes from: _tool + field, or file path_ (P2-T13)
- How media links are returned and downloaded: _…_

## Call recipes that worked (one line each; add during P2)

<!-- e.g. motion clip: load_model(...) → generate_video(...) → get_job(id, wait=…) → curl link → unload_model -->

## HyperFrames notes (P1-T07; CLI v0.8.188; skill at C:\Users\barrett\.claude\skills\hyperframes)
- **Entry file:** `index.html` (root composition — declares variables, mounts scenes from `compositions/`; media/fonts in `assets/`). Projects: `render/` (film) + `render_preview/` (previews).
- **Timed element:** `class="clip"` + `data-start` + `data-duration` (seconds), visible over `[start, start+duration)`. `data-track-index` is a Studio lane only; **paint order = `z-index`**.
- **Canvas:** html/body size + `<meta viewport width=1920 height=1080>` + root `data-width`/`data-height` = 1920×1080.
- **Seekable:** build ONE paused GSAP timeline per composition and register it AFTER its tweens — `window.__timelines["<data-composition-id>"] = tl; tl.seek(0);` — HyperFrames seeks it frame-by-frame, so renders are identical.
- **Determinism:** no `Date.now()`, unseeded `Math.random()`, network, timers, `repeat:-1`. Never tween `display`/`visibility`/`autoAlpha` on a `.clip`; don't mix CSS `transform` with GSAP transforms on the same element.
- **Media:** a `<video>` keeps sound only with `data-has-audio="true"`, else `muted`; music/voice = separate `<audio id=…>`; no `crossorigin`; time a video OR its wrapper, not both. (Film renders **silent**; final mix muxed by `tools/mux_final.py`.)
- **Footage grades/grain/vignette/blur** go through `hyperframes media-treatment`, not CSS filters. Fonts: bundled by name or `@font-face` to `assets/fonts/`. Asset paths root-relative.
- Validate with `npx hyperframes check --json` (fix errors) before render. Skill default is **30 fps**; this film overrides to **24 fps** (CONTEXT §5).
- **Template diff** (`templates/composition_example.html`): static — no `window.__timelines`. Real builder (P3-T05) MUST add the paused timeline; skill wins.

**Canonical render command** (run from `render/`; H.264, 1920×1080, 24 fps, high quality; frame cache kept on F: to avoid C: temp exhaustion):
`RENDER_CMD: cd render && npx hyperframes render . --resolution landscape --fps 24 --quality delivery --format mp4 -o "renders/<name>.mp4" --frames-cache-dir "F:/film-pipeline/.hf-cache"`
(tip: GPU is VRAM-contended per P1-T01 — on capture/GPU errors add `--no-browser-gpu`; on a heavy composition timing out add `--browser-timeout 120`.)
