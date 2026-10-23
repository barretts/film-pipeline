# Phase 2: Smoke-test every model

**Goal:** prove that each personal-lane model runs on this PC with the start settings in CONTEXT.md §4, and measure real VRAM use and time per item. Save small outputs in `tests/fixtures/` so P3 can test the tools on real files. Decide every fallback before production.
**Who:** the agent. The phase ends at ✋ P2-T15.
**Time:** 1–2 days, mostly downloads (~150–200 GB). Start the biggest downloads early: A14B, LTX-2.5, Qwen3.8-27B.

## Standard procedure for every smoke test
1. `studio_status`: if any GPU model is loaded, `unload_model` it (§3.1).
2. If `load_model` has a preview or dry-run option, check the download and unload plan first.
3. `load_model` with the variant from MODELS.md (or CONTEXT §4 if MODELS.md has no row yet).
4. Run **one** generation with the start settings. Always ask for media as a link or file. Save the output under `tests/fixtures/` with the name the task gives.
5. Long jobs: wait or poll as CONTEXT §8 describes. Media inputs are absolute paths (`<ROOT>/tests/fixtures/...`).
6. `unload_model`.
7. Run `.venv/Scripts/python tools/mcp_report.py --last 10`. Copy the peak VRAM and time per item into MODELS.md, and add a call recipe line to TOOLS.md.
8. Check the output's format with `ffprobe` (audio/video) or from the file size and dimensions (images). Record PASS or FAIL.

## Tasks
| ID | Model | Fixture(s) |
|---|---|---|
| P2-T01 | Qwen3.8-27B (writer) | writer_sample.md |
| P2-T02 | Qwen-Image-2.1-Turbo | portrait.png, scene.png |
| P2-T03 | reference/edit mode | ref_scene.png |
| P2-T04 | Wan2.2-TI2V-5B | motion_5b.mp4 |
| P2-T05 | Wan2.2-I2V-A14B | hero_a14b.mp4 |
| P2-T06 | LTX-2.5 (native audio) | talk_native.mp4 |
| P2-T07 | HTDemucs | talk_vocals.wav |
| P2-T08 | MOSS-Transcribe-Diarize | talk_vocals.transcript.json |
| P2-T09 | Breeze-TTS-2 | clone_t1-3.wav, design_t1.wav |
| P2-T10 | LTX-2.5 audio-driven (optional) | talk_a2v.mp4 |
| P2-T11 | YuE 2 | music_test.wav |
| P2-T12 | MiDashengLM-Gen | sfx_chalk_48k.wav, drone_test_48k.wav |
| P2-T13 | Qwen3-0.6B LoRA → GGUF | loss_test.csv, export info |
| P2-T14 | HyperFrames render | render_test.mp4 |
| P2-T15 | ✋ stack review | MODELS.md summary + contact sheet |

## Exit criteria
- Every MODELS.md row has a status (PASS, or a FALLBACK with its name) and measured numbers.
- TOOLS.md lists a working call recipe for each kind of generation.
- The human approved the stack in P2-T15.

## Notes
- Two small audio models (Breeze-TTS-2 + MOSS) may stay loaded together if ≥ 2 GB is still free (§3.1).
- If a model isn't in the Studio catalog, use the fallback listed in MODELS.md, record it, and carry on. Don't stall the phase.
