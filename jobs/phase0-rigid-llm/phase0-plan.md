# Phase 0 — Rigid LLM plan test (hand-built, 2 shots)

Film: "Signal in the Snow" (existing series world, characters already approved).
Goal: build ONE Lane A shot and ONE Lane B shot end to end, score them, decide the lane split.
Do NOT build Phase 1–4 automation in this folder.

## Recon (2026-11-15, verified on file-cabinet)

- GPU: RTX 4060 Ti, 1045 MiB / 16380 MiB used, 1% util. Strata off, no Ollama/Blender/ComfyUI running.
  Unsloth Studio healthy on 127.0.0.1:8888. Port 1234 still LISTENING (Strata supervisor only, no VRAM use).
- Disk: E: 345 GB free, F: 271 GB free.
- Blender 5.2.2 LTS at `F:\ue\Blender 5.2\blender.exe`, headless `--version` verified.
- ComfyUI: `F:\film-pipeline\comfy-local`, launched via `jobs\start_comfy_local.py`
  (SwarmUI ComfyUI source, port 8191, `--lowvram --offline`, whitelisted nodes only).
  NOT running at recon; start before renders.
- Video models actually installed (ComfyUI): MiniMax H3 ONLY — ref2va int8, fl2va fp8,
  Qwen3VL 32B encoder, video/audio VAEs, turbo LoRAs. No Wan/LTX ComfyUI models.
  Wan 2.2 TI2V 5B GGUF exists via Unsloth Studio (`tools/video_motion.py`, ~11.5 min / 4.5 s,
  ~15.5 GB VRAM) — not used in Phase 0; H3 is the installed renderer.
- Repo: branch `series`, HEAD 88f9132, working tree DIRTY (8 modified, ~15 untracked from
  prior Codex/OMP directing-layer work). Phase 0 commits go on branch `phase0-rigid-llm`,
  staging ONLY files under `jobs/phase0-rigid-llm/`. Do not stage or commit others' changes.
- Characters ready, no generation needed: Kate (C01) + James (C02) with portraits, orbit
  refs (frame-01/02/03), Piper voices kristin / joe. See `characters.json`.
- Proven render paths in this repo:
  - Lane A: `tools/minimax_speech.py submit` — H3 speech-driven, 124 frames @24 fps,
    704x1280, seed 2801, 8 steps. Owner-approved talking-shot workflow.
  - Lane B: NO full-video guide node exists in the installed H3 set. `MiniMaxH3AddGuide`
    anchors a guide image batch at `frame_idx`. The repo's `motion_ref` path
    (`local_film/pipeline.py`, VHS_LoadVideo `format:'H3'`, frame_load_cap = overlap)
    is the closest proven mechanism. Phase 0 Lane B reuses that construction with
    `frame_load_cap=124` (full guide) + `MiniMaxH3ReferenceToVideo` (Kate+James refs)
    + `SenseNovaH3DistilledBridge` — and measures empirically whether motion survives.
    If it only anchors frame 0, the score will show it. That IS the Phase 0 question.

## The two shots

### P0-A1 — Lane A (keyframe image-to-video, default). "Kate: the signal is holding"
Kate medium close-up at the radio desk, static camera, dialogue to camera.
First frame: `series/characters/kate/portrait.png`. Audio: Piper kristin TTS (see script.json).
Model: MiniMax H3 ref2va via `tools/minimax_speech.py`. 124 frames @24 fps = 5.17 s,
704x1280, seed 2801. Take name: `phase0-a1-kate-radio`.

### P0-B1 — Lane B (blockout-guided video-to-video). "James crosses to Kate"
Wide landscape 1280x704. James enters through the station door (frame left), walks to
Kate at the radio desk (frame right). Camera dollies right, tracking him. Kate turns
her head toward him as he arrives (last ~1.5 s). No dialogue; silent audio track.
Guide: Blender 5.2.2 Workbench render, capsules/boxes, 124 frames @24 fps.
Model: MiniMax H3 ReferenceToVideo + AddGuide (full 124-frame guide batch) + Kate/James
refs. Seed 5002. Take name: `phase0-b1-james-crosses`.

## Files in this folder

- `phase0-plan.md` — this file
- `script.json` — dialogue lines with speaker IDs and target durations
- `characters.json` — C01/C02 bible (pointers to existing series assets, no new art)
- `storyboard.json` — one 14-field row per shot
- `shots.json` — per-shot render contracts (lane, model, prompt, refs, frames, seed)
- `blender/p0-b1-blockout.py` — bpy script: builds the blockout, renders guide mp4 + frame 1 still
- `blender/p0-b1-blockout.blend` — saved scene (written by the script)
- `guide/p0-b1-guide.mp4` — Blender Workbench guide video (124 frames)
- `guide/p0-b1-frame-001.png` — single-frame validation still
- `comfy/p0-b1-build-graph.py` — builds the Lane B ComfyUI graph from
  `comfy-local/ref2va-audio-comparison-graph.json`, submits it, polls status
- `audio/p0-a1-kate-radio.wav` — Piper kristin TTS for the Lane A line
- `audio/p0-b1-silence.wav` — 5.17 s silent track for the Lane B graph (audio sync node needs input)
- `results/phase0-scores.md` — scores for both lanes (motion survival, character
  consistency, render time, human minutes) + Phase 1 lane-split recommendation
- `results/` — rendered clips, contact sheets, ffprobe logs, timing logs

## Scoring (fill in `results/phase0-scores.md`, do not invent)

Per lane: motion survival (did intended motion/camera survive?), character consistency
(same faces/clothes as refs?), render time on the 4060 Ti (minutes, timed), human minutes
(hands-on time, timed). Honest failures count as results.
