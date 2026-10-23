# TOOLS: Unsloth Studio MCP reference (filled in by P1-T05)

Keep this file under ~2,500 tokens: one line per tool, key parameters only. Never paste full schemas.

**Server name in Claude Code:** _fill in_ (tools appear as `mcp__<server>__<tool>`)
**Studio URL:** http://127.0.0.1:8888 (confirm) · **Studio version:** _fill in_ · **`unsloth doctor --mcp` verdict:** _fill in_

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
