# Local tools and evidence

Check current versions, availability and exact parameters before use. Record working recipes and evidence here; do not present release-note guesses as verified behavior.

| Tool | Known state | Next verification |
|---|---|---|
| Unsloth Studio | Local health endpoint at `http://127.0.0.1:8888/api/health` responded during the 2026-10-26 inspection. | Check health, model residency, catalog, exact tool schemas and output handling in the active session. |
| OMP + Studio MCP | A prior standard OMP CLI session reported 23 tools and a successful `studio_status`; hook events were verified in that client. Its hook is `.omp/hooks/post/unsloth-log.ts`, using `tools/log_mcp.py`. | Recheck the chosen client's actual invocation and logging before relying on its calls as film evidence. The old agent-mode bridge did not fire OMP hooks. |
| Strata | Optional local coding option; its engine was stopped with owner authorization during the 2026-10-26 preflight. | Select only if useful; recheck memory and running jobs before switching. |
| `tools/local_preflight.py` | Local baseline and resource check added during this implementation. | Run `.venv\Scripts\python.exe tools\local_preflight.py --require-studio --min-free-mib 12000`; confirm actual model requirements separately. |
| `tools/studio_mcp.py` | Direct local MCP calls succeeded and captured redacted records independent of client hooks. | Run `list`, `schema <tool>`, or `call <tool> --args '<JSON object>'`. The key is read from the environment or Windows user environment, never passed on the command line. |
| `tools/assemble_pilot.py` | Generated assets have been assembled and decoded successfully. | Use the manifest format below; inspect the resulting media and its content. |
| `tools/lipsync.py` | MuseTalk 1.5 runs locally on the RTX 4060 Ti and produces a talking portrait from supplied speech. | Run the command below after unloading other GPU models. |
| `tools/minimax_speech.py` | Preferred talking-shot workflow: MiniMax H3 generates character motion while conditioned on the recorded speech. | Use a unique take name; inspect the result and its audio before assembling a reel. |
| `tools/anime_lipsync.py` | Experimental CPU-only Rhubarb and tracked-mouth compositor for a single moving 2D shot. | Provide character-specific mouth artwork and review the animation and timing; the built-in marks are only a technical demo. |
| `tools/video_motion.py` | Wan2.2 TI2V 5B GGUF generated a portrait clip with real arm, head and body motion locally. | Run the command below with a new output path, then review visual quality. |
| FFmpeg / ffprobe | Resolved on PATH during inspection. | Use `ffprobe` to verify actual pilot/final media streams and duration. |
| HyperFrames | Starter projects exist in `render/` and `render_preview/`; a starter render was previously reported. | Read applicable project instructions before editing, then run the appropriate checks and inspect rendered frames. |
| `tools/contact_sheet.py` | Existing contact sheet utility. | Use for reviewing generated stills or representative video frames. |
| `tools/log_mcp.py` | Existing redaction and MCP logging utility. | Preserve source logs and validate capture and redaction when changing client or logger. |

For a fresh VRAM reading: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader`. For media inspection: `ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate,sample_rate,channels -show_entries format=duration -of json <file>`.

The pilot assembler expects JSON with shot paths relative to the manifest and a single audio track, for example:

```json
{"shots":[{"file":"../stills/shot.png","type":"image","duration":4}],"audio":"../audio/pilot.wav"}
```

Run `.venv\Scripts\python.exe tools\assemble_pilot.py edit\pilot.json --out render\pilot.mp4`. It creates hard cuts, trims or pads the audio and checks the output streams. It does not add captions, mix multiple tracks, or verify factual provenance; it will not replace an existing output without `--overwrite`.

## Preferred speech-driven MiniMax shots

The owner compared the local audio-driven test with the previous mouth-replacement approach and approved it as a significant improvement. Use this workflow first for new talking shots. MiniMax H3 receives the recorded speech as a locked audio latent and guide while generating the character's motion; the saved shot carries the supplied recording. Do not apply a second lip-replacement pass by default. LatentSync and MuseTalk remain fallbacks for existing footage or shots that need a separate fix.

Start the isolated project ComfyUI if it is not already running: `E:\SwarmUI\dlbackend\comfy\ComfyUI\venv\Scripts\python.exe jobs\start_comfy_local.py`. Its local endpoint is `http://127.0.0.1:8191`; the launcher enables only the workspace-local `film_h3_audio` adapter and runs with low VRAM and partner/cloud nodes disabled. Preserve the MiniMax models under `comfy-local/models/` and the workspace checkout `comfy-local/custom_nodes/ComfyUI_LC_AV_nodes/`; the adapter loads its [LC H3 Audio Sync node](https://github.com/lonecatone23/ComfyUI_LC_AV_nodes) without enabling the whole pack. All inference is local.

Submit a uniquely named shot from the project root:

```powershell
& '.venv\Scripts\python.exe' tools\minimax_speech.py submit --name 'example-take-01' --image 'stills\reels\full-motion\01.png' --audio 'audio\reels\01-paced.wav' --prompt 'The woman speaks the supplied recording naturally while moving her head and hands. Maintain the character, clothing, room and hand-drawn style.'
& '.venv\Scripts\python.exe' tools\minimax_speech.py status --name 'example-take-01'
```

The default is 124 frames at 24 fps (5.17 seconds), 704x1280, seed 2801 and eight sampling steps. Source inference remains 704x1280; a 1080x1920/30fps reel is a later export. `--audio-start` selects the part of a recording for a continuation; `--frames` must be `17k+5` and at most 362. The command refuses to run beyond the recording unless `--allow-trailing-silence` is explicitly supplied. It records the input hashes, graph and ComfyUI job ID under `comfy-local/speech-jobs/`, refuses to overwrite a take, and blocks blind retries after an ambiguous submission. Completed output is under `comfy-local/output/minimax-speech/`. Inspect output, character continuity and lip sync with sound; numeric audio matching does not prove mouth accuracy. For longer scenes, plan the shots and source-audio offsets deliberately, check joins, and avoid cutting speech mid-word. The approved five-second test is `comfy-local/output/minimax-audio-test/anime-01_00001_.mp4`.

## Local lip sync

With the installed project environment and model weights, run from `F:\film-pipeline`:

```powershell
& '.venv\Scripts\python.exe' tools\lipsync.py --image 'stills\lipsync\character.png' --audio 'audio\lipsync\character.wav' --out 'video\lipsync\new-take.mp4'
```

Supply any readable PNG/JPEG portrait and audio file; a clear front-facing face works best. The command runs offline, keeps the input audio's sample rate, writes a detailed `logs/lipsync-*.log`, validates both streams and duration, and leaves an existing output intact unless `--overwrite` is specified. The current MuseTalk engine uses unquoted intermediate shell paths, so the project root itself must not contain spaces or shell metacharacters. Input and output paths may contain spaces because they are staged internally. Check free GPU memory and unload competing models before running.

The current installation is `tools/MuseTalk/` at commit `0a89dec45a0192b824e3cf4daf96c239440c5ed8`, Python 3.10.22 and CUDA PyTorch 2.0.1+cu118 in `venvs/musetalk/`. Both directories and downloaded weights are intentionally ignored by git and must be preserved on this machine. `tools/musetalk-windows.patch` records the still-image cleanup fix applied to the checkout. Required weights include MuseTalk V1.5, Stable Diffusion VAE, Whisper tiny, DWPose, face parsing, and S3FD. If rebuilding, use the upstream MuseTalk instructions and apply that patch; this installation uses mmcv 2.0.1 for Windows/cu118/PyTorch 2.0, mmdet 3.1.0, mmpose 1.1.0, diffusers 0.30.2, transformers 4.39.2 and NumPy 1.23.5. Different machine environments have not been verified.

## Experimental tracked 2D mouth animation

`tools/anime_lipsync.py` uses the existing MuseTalk Python environment and DWPose weights **on CPU**, then places mouth artwork on the original forward-moving footage. It is an experiment: the tracker can report confident but wrong landmarks, the cues can be inaccurate, and the small inpaint patch can fail on a turning or occluded face. Watch and listen to every output; a successful run is not a lip-sync quality certification. The built-in mouth marks are deliberately crude and are not final artwork.

For this machine's tested anime shot, run the demo in a new output path:

```powershell
& 'venvs\musetalk\Scripts\python.exe' tools\anime_lipsync.py --video 'video\full_motion\anime-quality.mp4' --audio 'audio\lipsync\character.wav' --transcript 'jobs\anime_pose_experiment\dialog.txt' --face-crop '128,24,448,448' --demo-shapes --out 'jobs\anime_pose_experiment\new-demo.mp4'
```

`--face-crop` is a fixed square `x,y,width,height` in source-video pixels; choose a crop that contains the same unobstructed face throughout a single shot. DWPose estimates 68 landmarks in the 512-pixel crop. The command rejects an absent/low-confidence/out-of-bounds face, implausible mouth, or sudden landmark jump on any frame, rather than skipping or looping frames. It cannot guarantee the person or landmarks are correct when model confidence is misleading. The source video must last at least as long as the decoded speech. Input motion is normalized to 25 fps with `floor(speech_seconds * 25)` forward frames; speech is kept whole, so its final partial frame can extend up to 40 ms beyond the video. The command validates output streams and full decoding; an existing output is preserved unless `--overwrite` is supplied.

To use real artwork, replace `--demo-shapes` with `--art-dir 'path\to\mouth-art'`. The directory must contain transparent RGBA PNGs named for each used cue: `A.png` through `F.png`, plus `G.png` and `H.png` if those cues occur. Cue `X` keeps the original resting mouth. Center each drawing on a transparent canvas with consistent dimensions and transparent margins; the image is scaled to the tracked mouth-corner width, rotated with the head, and overlaid after inpainting the original mouth stroke. `--mouth-width-scale` adjusts the width from 0.5 to 2.0. Each drawing should match the character and cue rather than reusing the demo's simple ellipses. See [Rhubarb's mouth-shape guide](https://github.com/DanielSWolf/rhubarb-lip-sync#mouth-shapes).

Rhubarb 1.14.0 is installed at ignored `venvs/rhubarb/` from its [official Windows release](https://github.com/DanielSWolf/rhubarb-lip-sync/releases/tag/v1.14.0); keep the executable, `res/`, and license file together. `--transcript` supplies the UTF-8 dialogue to Rhubarb; alternatively use `--cues path\cues.json` for existing Rhubarb-format `mouthCues`. Cue intervals must be continuous, use supported letters, and cover the decoded speech. The code uses MIT-licensed Rhubarb and separately installed model dependencies; check the actual voice and media terms for publication. The tested 4.49-second sample produced 112 valid tracked frames and a fully decoded experimental output; the cue sequence shifted by one second in a delayed-speech control. This does not establish natural phoneme synchronization or artistic quality.

## Local full-motion video

After checking that Studio has no competing GPU jobs, use a new output name:

```powershell
& '.venv\Scripts\python.exe' tools\video_motion.py --image 'stills\reels\full-motion\01.png' --prompt 'The woman looks down at the watch in her hands, then raises her eyes; her hands, shoulders and hair move naturally. Keep the camera still.' --out 'video\full_motion\new-take.mp4' --size 704x1280 --frames 73 --fps 16 --steps 16
```

The command uses Studio's Wan2.2 TI2V 5B GGUF Q4_K_M in low-VRAM mode. It saves a `<output>.wan-job.json` sidecar containing the request, source hash, load/video job IDs, status and verified measurements; it does not store the Studio key or signed download URL. To resume a `loading` or `generating` job, rerun the same command with unchanged inputs. If the state says `unknown_submit`, inspect Studio's recent video jobs before taking any action: automatic replay is blocked to prevent a duplicate render. Existing output files are never overwritten. The downloaded model cache and Studio installation must remain available.

On this machine, the first 73-frame portrait test took about 11 minutes 31 seconds for 4.56 seconds of 16 fps source motion; a GPU sample reached roughly 15.5 of 16 GiB. See `video/full_motion/anime-quality.mp4` and `logs/anime-quality-contact.jpg`. The character's head and arms visibly move; a carried watch drifts in shape/position. Movement measurements alone do not establish visual or character quality. Source motion is 16 fps and is not a finished Instagram reel; compose and export the final reel at 1080x1920 and 30 fps. A short 4-step trial was badly distorted, so do not use it as a quality reference.

An existing OMP configuration points to an optional Strata server on `127.0.0.1:1234`. Its configured selector is `omp --model strata-q4/qwen3.8-flash-next-ud-q4_k_xl-128k-low-ram`; a 32K selector is also configured. After Studio jobs are finished and its GPU models unloaded, use Strata's existing UI to restart its engine, then launch OMP from this project. A supervisor still answered on port 1234 after the engine stopped, so check the UI before launching another server. The selector and model configuration were inspected but local coding inference and resume have not been tested.

## Provenance

`logs/mcp_calls.jsonl` and `logs/mcp_raw/` contain historical captured call evidence. Do not edit or invent entries. The hook applies only where the client actually emits compatible events. A successful generation without verified capture may be used as media, but it does not prove an on-screen factual claim. Store job IDs, output paths and inspection results in the handoff or a project record, without secrets or large payloads.
