# CONTEXT: stable facts for every session

Read this every session. Tasks refer to its sections as §1–§10. Measured numbers, catalog ids and **production settings** live in MODELS.md, and tool details in TOOLS.md. Don't copy them here.

## §1 Project

You are making a **60–90 s (target 75 s)** mysterious, slow-burn, A24-style short promo, described in `brief.md`. Everything uses **local models only**, driven through **Unsloth Studio's MCP server**. You are the director.

This is **personal, non-commercial use only**, because of these licenses:
- Qwen-Image-2.1-Turbo: research license.
- Breeze-TTS-2: non-commercial, including self-hosted outputs.
- YuE 2: CC BY-NC 4.0.
- LTX-2.5: LTX-2.x Community License.

## §2 Machine

- Windows 11 Pro · AMD Threadripper 1950X (16C/32T, AVX2) · **128 GB DDR4** (quad-channel).
- **NVIDIA RTX 4060 Ti 16 GB** (Ada: FP8 yes, NVFP4 no) on a **PCIe 3.0 x8** link. Offloading to RAM works, but it is slow.
- Models are stored under `HF_HOME` on the model drive. The project root (Windows form) is in the STATUS.md header.
- Unsloth Studio runs at `http://127.0.0.1:8888`, with MCP at `/mcp/`. Confirm both in P1.

## §3 Golden rules

1. **One GPU model loaded at a time.**
   - Check `studio_status` before every load, and unload first.
   - Exception: two small audio models (TTS + ASR) may share the GPU if ≥ 2 GB is still free after both load.
2. **Local models only**, through the Unsloth Studio MCP tools. Use a fallback engine from MODELS.md only when a task says so. Never use cloud generation APIs.
3. **Truth rule.** Anything on screen must come from `logs/mcp_calls.jsonl` or `logs/mcp_raw/`. That includes feature and tool names, model names, numbers, timings, the loss curve, and caption text. `tools/facts.py check` enforces this from P3-T03 on. Never invent values, and never edit logs.
4. **Consent.** The voice is generated (LTX-2.5) or designed (Breeze-TTS-2). Never clone a real person.
5. **Secrets.** The Unsloth API key lives only in the user environment variable `UNSLOTH_API_KEY`.
   - Never print, write, or ask for it.
   - Never run `env`, `printenv`, `set`, `Get-ChildItem Env:`, or `echo $UNSLOTH_API_KEY`.
   - If it is ever exposed, ask the human to rotate it in Studio › Settings › API.
6. **Personal lane only.** Use the models in §4 and MODELS.md. Ask before any swap.
7. **Ask the human (✋)** at checkpoints, and before any of these:
   - admin rights;
   - license click-throughs;
   - installing community binaries or custom nodes (give the link and what it does);
   - changing `.claude/settings.json` or `tools/log_mcp.py` after they were approved;
   - deleting non-temporary files.

## §4 Models (personal lane; MODELS.md records the exact ids)

| Role | Model | Default settings | License / notes |
|---|---|---|---|
| Writer | Qwen3.8-27B GGUF **UD-Q4_K_XL** (fallback UD-Q3_K_XL) | ctx 32k; save only the final answer (instruct mode, or strip any thinking block); `reasoning_effort` medium allowed for the production prompt. Instruct: temp 0.7, top_p 0.8, presence_penalty 1.5 | Apache-2.0; auto-offload to RAM |
| Stills | Qwen-Image-2.1-Turbo GGUF **Q4_K_M** | 8 steps (built-in schedule), CFG 1, fixed seed per shot | Qwen Research License |
| Reference shots | Qwen-Image-2.1-Turbo edit/reference; else Qwen-Image-Edit-2511 | master portrait as reference (≤ 3 images) | chosen in P2-T03 |
| Motion video | Wan2.2-TI2V-5B **GGUF** (catalog `low_vram` row) | start frame, 1280×704, 121 frames, 24 fps | Apache-2.0 |
| Hero video | Wan2.2-I2V-A14B GGUF **Q5_K_M** (Q4_K_M fallback) | 832×480, 81 frames, 16 fps, CPU offload | Apache-2.0; queue in the evening |
| Talking video | LTX-2.5 (distilled) | start frame, 896×512, frames 8n+1, 24 fps, audio on; audio-driven if supported (P2-T10) | LTX-2.x Community License |
| Voice isolation | HTDemucs (Studio "Separate") | vocals stem | MIT |
| Voice | Breeze-TTS-2 | clone: reference 6–15 s + **exact** transcript; design/direction: instruction + cfg 4; inline events `(sigh)` | non-commercial; 24 kHz output |
| Music + vocals | YuE 2 (YuE2-3B) | style prompt + lyrics, cot full | CC BY-NC 4.0; 48 kHz stereo |
| SFX + drone | MiDashengLM-Gen | 5–20 s per cue; drones looped in the mix | Apache-2.0 + use policy; 16 kHz output |
| Transcribe / QA | MOSS-Transcribe-Diarize 0.9B | timestamps + speaker labels | Apache-2.0 |
| Fine-tune | Qwen3-0.6B LoRA → GGUF **Q4_K_M** | r 16, alpha 16, lr 2e-4, 100–200 steps, seq 1024 | Apache-2.0 |
| Render | HyperFrames + FFmpeg | 1920×1080, 24 fps; silent render, then mux | Apache-2.0 / LGPL |

## §5 Media standards (defaults; MODELS.md › Production settings overrides them)

- **Stills:** 1344×768 PNG. **Character master:** 1024×1024.
- **Clips:**
  - motion 1280×704, 121 frames, 24 fps (5.04 s);
  - hero 832×480, 81 frames, 16 fps (5.06 s);
  - talking 896×512, frames = smallest 8n+1 ≥ 24 × max(shot + 0.2, line + 0.6).
- **In-point:** the EDL starts every clip 0.2 s in to skip warm-up frames. So **motion/hero shots are ≤ 4.8 s**.
- **Still shots** (≤ 6 s) become clips with a slow push-in (P6-T04).
- **Final film:**
  - video: 1920×1080, 24 fps, H.264 yuv420p;
  - audio: AAC 320 kbps, 48 kHz stereo;
  - clips are scaled with `object-fit: cover`.
- **Audio working format:** WAV 48 kHz, 24-bit (`pcm_s24le`). Resample Breeze (24 kHz) and MiDashengLM-Gen (16 kHz) when importing.
- **Mix:** −14 LUFS integrated, true peak ≤ −1.5 dBTP, music ducked 8–12 dB under voice.
- **Voice-over lines:** ≤ 12 words and ≤ 4.5 s (`max_seconds` required). **Talking lines:** ≤ 10 words.
- **Film:** 18–22 shots, 70–80 s.

## §6 Folder layout (project root = this folder)

```
CLAUDE.md README.md START_HERE.md CONTEXT.md STATUS.md brief.md TOOLS.md MODELS.md
phases/ tasks/ templates/ tools/
logs/           mcp_calls.jsonl  mcp_raw/  vram.csv  sheets/  tasks/<ID>.md (+ <ID>.out for noisy output)
tests/fixtures/ smoke-test outputs (P2), used to test the tools (P3)   tests/samples/  synthetic test inputs
jobs/           batch manifests (*.json; schema templates/manifest.schema.json)
pilot/          the whole 15 s pilot (P4): script/ stills/ video/ audio/ captions/ edit/ mix/
script/         features.json  production_prompt.md  shot_list.json  lyrics.txt  lines.txt
stills/         character_master.png  character_sheet.png  <shot>_still.png  candidates/
video/          motion/  hero/  talking/  candidates/
audio/          ref/  vo/  dialogue/  music/  sfx/
captions/  train/  edit/ (edl.json, facts.json, picks.json)  mix/
render/         HyperFrames project (final.mp4)     render_preview/  separate HyperFrames project for previews
```

## §7 Naming

- **Ids:** shots `s01…s30`, voice-over lines `v01…`, sound cues `x01…`, takes `t1, t2…`.
- **Takes** are named `<id>_<kind>_<take>.<ext>`. Kinds: `still`, `vid`, `talk`, `vo`, `dlg` (talking-line audio), `sfx`, `music`. Example: `s07_vid_t1.mp4`.
- **Picks** drop the take: `s07_vid.mp4`, `v03_vo.wav`, `s05_dlg.wav`. They are recorded in `edit/picks.json` (schema `templates/picks.schema.json`).

## §8 Using the MCP server (details in TOOLS.md after P1-T05)

- **Tool names** follow `mcp__<server>__<tool>`. Expected tools, from the Unsloth release notes (confirm in P1-T05):
  - models: `studio_status`, `list_models` (source local/catalog + workflow filter), `load_model`, `unload_model`;
  - text: `chat`;
  - media: `generate_image`, `generate_audio` (clone, speak, edit, convert, music, separate), `transcribe`, `generate_video` (returns a job/queue id);
  - training and data: `start_training`, `list_training_runs`, `export_model`, `datasets`, `run_recipe`;
  - jobs: `get_job`, `cancel`.
- **Paths in:** use **absolute Windows paths with forward slashes**, e.g. `X:/film-pipeline/stills/s01_still.png`. Take the root from the STATUS.md header (`pwd -W` in Git Bash). Studio can't resolve relative paths or `/x/...` paths. Manifests store project-relative paths; prepend the root when calling.
- **Media out:** ask for a link or file (`return_media: "link"` or equivalent), never inline. Download with:
  ```bash
  curl -fsS -o <path> "<link>"
  ```
- **Long jobs:**
  1. Prefer `get_job`'s wait/follow option: one call per job.
  2. Otherwise, sleep about ¼ of the expected job time from MODELS.md between polls (60–300 s per `sleep`, chained if needed), and log one line per poll.
  3. The video queue holds ≤ 32 clips. Queue only clips for the model that is currently loaded.
- **Logging:** every MCP call is logged by the hook (P1-T03). Never log by hand.

## §9 Context budget (128k window)

- **Per session**, load only: CLAUDE.md, START_HERE.md, this file, STATUS.md, the current phase and task files, and TOOLS.md/MODELS.md when the task asks. That's about 12–15k tokens.
- **Never `cat`, `tail` or `grep` `logs/mcp_calls.jsonl` or `logs/mcp_raw/`.** Their lines are large. Use `tools/mcp_report.py` (`--last N`, `--seq-only`).
  - For other big files, use `tail -n 5`, `head -c 2000` or a summary script.
  - The only exception is the setup checks in P1-T03.
- **Noisy commands** (ffmpeg, npx, pip, renders): run them quietly (`-hide_banner -loglevel error -nostats`, `pip -q`), or redirect output to `logs/tasks/<ID>.out` and `tail -n 5` it.
- **Images:** look at them only as contact sheets (`tools/contact_sheet.py`), ≤ 16 tiles each.
- **Batches per session:** ≤ 8 image/video items, or ≤ 24 audio takes. Manifests make the work resumable.
- **Context use:** start a new task only below ~50% context. If you pass ~60% in the middle of a task, write a handoff and stop.
- **Notes:** details go to `logs/tasks/<ID>.md`. STATUS.md gets one line per task.

## §10 Shell and commands

- **Agent shell:** Git Bash (Claude Code on Windows), with forward slashes. Project Python is `.venv/Scripts/python`; the hooks use system `py -3`.
- **Human steps** are marked **[HUMAN · PowerShell]**.
- **Reference commands:**
  - VRAM now:
    ```bash
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader
    ```
  - Probe a file:
    ```bash
    ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate,sample_rate,channels -show_entries format=duration -of json FILE
    ```
  - Extract audio:
    ```bash
    ffmpeg -hide_banner -loglevel error -nostats -y -i in.mp4 -vn -ac 2 -ar 48000 -c:a pcm_s24le out.wav
    ```
  - Resample:
    ```bash
    ffmpeg -hide_banner -loglevel error -nostats -y -i in.wav -ar 48000 -ac 2 -c:a pcm_s24le out.wav
    ```
  - Trim:
    ```bash
    ffmpeg -hide_banner -loglevel error -nostats -y -ss START -to END -i in.wav -c:a pcm_s24le out.wav
    ```
  - Last calls, or seq numbers for manifests:
    ```bash
    .venv/Scripts/python tools/mcp_report.py --last 10
    .venv/Scripts/python tools/mcp_report.py --last 3 --seq-only
    ```
  - Render: always use the canonical command recorded in TOOLS.md › HyperFrames notes (P1-T07).
