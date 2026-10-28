# Local film pipeline: installation and operation for an installing agent

This guide is for a coding agent working with an operator on a new Windows machine. The repository must be available from GitHub, but no models, runtimes, ComfyUI, Python environments or custom nodes are assumed to be present. Work inside the new project directory. Do not alter an existing ComfyUI, SwarmUI, Strata, Python installation, model directory, or user output. Do not put API keys or tokens in Git. The pipeline uses no cloud inference or external orchestration. Network access is needed for installation only.

**Validation scope:** The pipeline was exercised on the machine described below. The install commands were checked against the repository implementation, downloaded assets, pinned source revisions, the installed package metadata, and the upstream sources linked below. A fresh-machine installation was not performed. New-machine installation steps and alternative hardware remain untested; stop and report discrepancies instead of silently substituting versions.

## 1. Requirements and discovery

Tested: Windows 11 x64, Python 3.13.15 x64, NVIDIA RTX 4060 Ti 16 GiB, NVIDIA driver 591.86, 127.9 GiB system RAM, ComfyUI 0.38.0 commit `65787d668397d230bf5839d69a0a7239e2dad378`, PyTorch 2.11.0+cu130, and FFmpeg 8.0.1 full build. Generation uses `--lowvram` and CPU offload; sampled GPU use reached about 15.2 GiB. The installation helper provides FFmpeg 8.0.1 essentials, whose same commands should work but whose build differs from the originally tested full build.

Required for this implementation: Windows x64; a CUDA-capable NVIDIA GPU and working `nvidia-smi`; Python 3.13 x64; Git; the tested CUDA 13 PyTorch build; enough free GPU memory for the graph; access to GitHub and Hugging Face during installation; and space for weights and outputs. The worker waits for at least 12,000 MiB of free VRAM, for up to two hours. It does not establish that every 12 GiB card can run the graph. NVIDIA documents driver branch 580 or later for CUDA 13 minor-version compatibility: <https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html>. Driver 591.86 is the tested value. A separate CUDA toolkit installation is not required by the tested binary PyTorch runtime.

Recommended: at least 16 GiB VRAM, 128 GiB system RAM and 250 GiB free on the project volume. These are the tested/comfortable profile, not proven minimums. The required base model plus encoder, VAEs, adapters, planner and runtimes use about 50 GB decimal; the FL2VA fallback adds about 23 GB. Installation caches, wheels, temporary copies and videos need additional space. Less RAM/VRAM, older GPUs, Linux, macOS and alternative CUDA builds have not been tested. Stop and ask the operator before choosing an untested configuration.

Install Git for Windows and 64-bit Python 3.13 from their official installers if absent: <https://git-scm.com/download/win>, <https://www.python.org/downloads/windows/>. Installation of system software is an operator action; do not remove or replace another version. Verify `git --version` and `py -3.13 -c "import sys; print(sys.version, sys.maxsize > 2**32)"`. Expected: Git prints a version; Python reports 3.13 and `True`.

Get the repository URL and an empty destination from the operator. The repository currently has no configured Git remote in the tested workspace, so this guide cannot supply a real URL. In PowerShell, substitute the operator-provided values; never leave the placeholder text:

```powershell
$FilmRepoUrl = 'OPERATOR_PROVIDED_GITHUB_REPOSITORY_URL'
$FilmProject = 'OPERATOR_PROVIDED_EMPTY_ABSOLUTE_DIRECTORY'
if ($FilmRepoUrl -like 'OPERATOR_*' -or $FilmProject -like 'OPERATOR_*') { throw 'Obtain the repository URL and destination from the operator.' }
if (Test-Path -LiteralPath $FilmProject) { throw 'Destination exists. Stop and ask the operator; do not overwrite.' }
git clone -- $FilmRepoUrl $FilmProject
if ($LASTEXITCODE -ne 0) { throw 'Repository clone failed.' }
Set-Location -LiteralPath $FilmProject
py -3.13 -m local_film.discover
```

Read the JSON before proceeding: GPU name, driver and total/free VRAM; RAM; free disk; tools; and whether loopback ports 8191 and 8765 are occupied. The discovery code is read-only. If 8191 is occupied, verify that it is the intended isolated ComfyUI before proceeding; do not kill or replace an unknown process. If 8765 is occupied, choose another form port as shown below. If storage is inadequate, ask for a larger project volume. Do not assume the GPU, driver, installed software or port availability from this guide.

## 2. Create a project-local ComfyUI environment

These commands create new directories only under this repository. If either destination already exists, stop and inspect it with the operator; do not run a clone or venv creation over it. Use the tested commit rather than updating another installation. The tested ComfyUI is the newest usable installation found on the original machine, not a claim about what is newest on a future machine.

```powershell
if (Test-Path -LiteralPath '.\local-runtime\ComfyUI') { throw 'ComfyUI destination exists; inspect before proceeding.' }
if (Test-Path -LiteralPath '.\local-runtime\venv') { throw 'Environment destination exists; inspect before proceeding.' }
New-Item -ItemType Directory -Force -Path '.\local-runtime' | Out-Null
git clone --no-checkout https://github.com/Comfy-Org/ComfyUI.git .\local-runtime\ComfyUI
if ($LASTEXITCODE -ne 0) { throw 'ComfyUI clone failed.' }
git -C .\local-runtime\ComfyUI checkout --detach 65787d668397d230bf5839d69a0a7239e2dad378
if ($LASTEXITCODE -ne 0) { throw 'Pinned ComfyUI checkout failed.' }
git -C .\local-runtime\ComfyUI rev-parse HEAD
py -3.13 -m venv .\local-runtime\venv
$FilmPython = (Resolve-Path '.\local-runtime\venv\Scripts\python.exe').Path
& $FilmPython -m pip install --no-deps --index-url https://download.pytorch.org/whl/cu130 torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130
if ($LASTEXITCODE -ne 0) { throw 'CUDA 13 PyTorch install failed.' }
& $FilmPython -m pip install -r .\local-runtime\ComfyUI\requirements.txt httpx==0.28.1 huggingface-hub==1.33.0
if ($LASTEXITCODE -ne 0) { throw 'ComfyUI dependencies failed.' }
& $FilmPython -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

Expected commit is exactly the hash above. The last line should report `2.11.0+cu130`, `13.0`, and `True`. If it does not, stop; do not install a different CUDA build into an existing environment. PyTorch's official selector is <https://pytorch.org/get-started/locally/>. This workflow's VSA node requires the `comfy-kitchen` CUDA `sol_attn` capability; the original cu128 environment disabled ComfyUI's CUDA backend, so a cu128 install is not a tested equivalent. The pinned ComfyUI requirements specify `comfy-kitchen==0.2.36`, `comfy-aimdo==0.5.5`, frontend `1.53.10` and templates `0.11.74`.

## 3. Download local inference runtimes and all model assets

The scripts use direct, pinned downloads and write under this repository. They do not enable cloud inference. Read the model and voice licenses before installation and stop if the operator cannot accept the applicable terms. In particular, the MiniMax community terms and the FastVideo gate's linked terms apply to those assets; the Amy voice model card points to its underlying dataset license, so its downstream use should be reviewed. Qwen3.5-4B is listed as Apache-2.0. The prior Qwen2.5-3B experiment used a research-only license and is **not** the default. Piper's tested release code is MIT; its voice has separate terms. Sources: <https://huggingface.co/Comfy-Org/MiniMax-H3>, <https://huggingface.co/barelymining/ComfyUI-MiniMax-H3-FastVideo>, <https://huggingface.co/lightx2v/Minimax-h3-Turbo>, <https://huggingface.co/speach1sdef178/MiniMax-H3-Semantic-Bridge>, <https://huggingface.co/unsloth/Qwen3.5-4B-GGUF>, <https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/amy/medium/MODEL_CARD>, <https://github.com/rhasspy/piper/blob/master/LICENSE.md>.

```powershell
& $FilmPython tools\setup_local_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime install failed. Preserve files and inspect the error.' }
& $FilmPython tools\download_local_planner_voice.py
if ($LASTEXITCODE -ne 0) { throw 'Planner/voice download failed. Preserve partial files and inspect the error.' }
$env:HF_HUB_DISABLE_XET = '1'
& $FilmPython tools\download_ref2va_http.py
if ($LASTEXITCODE -ne 0) { throw 'Ref2VA download failed. Preserve the partial file and investigate.' }
& $FilmPython tools\download_ref2va_comparison.py
if ($LASTEXITCODE -ne 0) { throw 'Ref2VA adapters failed. Inspect before retrying.' }
& $FilmPython tools\download_minimax_models.py
if ($LASTEXITCODE -ne 0) { throw 'Shared/fallback models failed. Inspect before retrying.' }
& $FilmPython tools\install_comfy_nodes.py
if ($LASTEXITCODE -ne 0) { throw 'Custom-node installation did not match pinned revisions.' }
& $FilmPython -m pip install -r .\comfy-local\custom_nodes\ComfyUI-KJNodes\requirements.txt -r .\comfy-local\custom_nodes\ComfyUI-VideoHelperSuite\requirements.txt -r .\comfy-local\custom_nodes\Comfyui-Memory_Cleanup\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Custom-node dependencies failed.' }
& $FilmPython tools\verify_local_assets.py --hash --fallback
if ($LASTEXITCODE -ne 0) { throw 'Asset verification failed. Do not use mismatched files.' }
```

`setup_local_runtime.py` installs llama.cpp CPU build `b11941`, Piper `2023.11.14-2`, and FFmpeg 8.0.1 essentials under `local-runtime`. It verifies archive SHA-256 values and refuses to replace differing extracted files. `download_local_planner_voice.py` resumes partial transfers and checks fixed hashes. The Ref2VA direct downloader checks size and hash and preserves the partial file on error; the other model downloaders verify existing weights and stop on mismatch. Do not delete partial or existing files to make a check pass. The large `--hash` verification reads every byte and can take several minutes.

Required models and paths (sizes are decimal bytes, rounded):

| Role | Source revision | Path under project | Size |
|---|---|---|---:|
| Local planner | `unsloth/Qwen3.5-4B-GGUF` `e87f176479d0855a907a41277aca2f8ee7a09523` | `local-runtime/models/Qwen3.5-4B-Q4_K_M.gguf` | 2.74 GB |
| Local voice | `rhasspy/piper-voices` `5041a7a49ae5b3a0f30e6837769eb03fdbb231bd` | `local-runtime/models/en_US-amy-medium.onnx` and `.onnx.json` | 63.2 MB + 4.9 KB |
| Ref2VA model | `Comfy-Org/MiniMax-H3` `e5eb578a89295337b8ff433a035929ce0279e0b6` | `comfy-local/models/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 20.97 GB |
| Text encoder | same MiniMax revision | `comfy-local/models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15.69 GB |
| Video VAE | same | `comfy-local/models/vae/minimax_h3_video_vae_fp16.safetensors` | 5.21 GB |
| Audio VAE | same | `comfy-local/models/vae/minimax_h3_audio_vae_fp32.safetensors` | 605 MB |
| 4-step LoRA | `lightx2v/Minimax-h3-Turbo` `30f485ed874aa44c8183348ad361c5eabad318da` | `comfy-local/models/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.96 GB |
| VSA gate | `barelymining/ComfyUI-MiniMax-H3-FastVideo` `aa554050fe27ec3c62e20e57519beb46741c9000` | `comfy-local/models/loras/fasth3_vsa_gate.safetensors` | 3.85 GB |
| Semantic Bridge | `speach1sdef178/MiniMax-H3-Semantic-Bridge` `b9fe58ba6f428d990a59f20f09f719c8fbc67f7d` | `comfy-local/models/semantic_bridge/MiniMaxH3_SemanticBridge_v1.safetensors` | 11 MB |
| Existing FL2VA fallback | same MiniMax revision | `comfy-local/models/diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors` | 20.96 GB |
| Existing fallback LoRA | same MiniMax revision | `comfy-local/models/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.96 GB |

The exact per-file hashes are executable data in `tools/verify_local_assets.py`; use `--hash --fallback` to verify all rows. The Semantic Bridge node archive is `comfy-local/downloads/MiniMax_H3_Semantic_Bridge_v1.0.zip`, SHA-256 `c4866a0cc554237046814c9cb827a5960caecbd2214d5a5a04b0e43716b437bb`. The helper checks it before extraction. Custom-node repositories and exact commits are in `tools/install_comfy_nodes.py`; the script verifies clean matching checkouts and never checks out over a changed existing directory. `film_h3_audio` is repository-backed and loads the narrow LC H3 audio-sync node from the pinned LC checkout. The optional NVIDIA 2× VFX upscaler is not required for the unattended pipeline; it is not installed by these commands.

## 4. Start and verify local components

Run the form and worker with the same environment so child processes inherit configuration. The server binds loopback only. The planner starts a temporary `llama-server` on a dynamically chosen loopback port and uses CPU; Piper is a local CPU subprocess; the worker sends local API requests to ComfyUI at `127.0.0.1:8191`; FFmpeg reads and writes local files. The worker automatically starts the isolated ComfyUI if it is absent. If the port is occupied by an incompatible service, stop and ask the operator.

```powershell
$env:LOCAL_FILM_COMFY = (Resolve-Path '.\local-runtime\ComfyUI').Path
$env:LOCAL_FILM_COMFY_PYTHON = (Resolve-Path '.\local-runtime\venv\Scripts\python.exe').Path
$env:LOCAL_FILM_PORT = '8765'
& $FilmPython -m local_film.server
```

Expected: `Local film form: http://127.0.0.1:8765`. Open that address on the same computer. After installation, double-click `Start-Local-Film.cmd` from the project folder to start the server and open the form in a browser; keep its terminal open. If port 8765 was occupied, set `LOCAL_FILM_PORT` to a verified free port instead and use that address. Leave this terminal running. A separate verification terminal can use:

```powershell
$FilmPython = (Resolve-Path '.\local-runtime\venv\Scripts\python.exe').Path
& $FilmPython -m unittest discover -s tests -p test_local_film.py
$FilmPreviousTemplate = [Environment]::GetEnvironmentVariable('LLAMA_ARG_CHAT_TEMPLATE_KWARGS', 'Process')
try {
  $env:LLAMA_ARG_CHAT_TEMPLATE_KWARGS = '{"enable_thinking":false}'
  & .\local-runtime\llama\llama-cli.exe -m .\local-runtime\models\Qwen3.5-4B-Q4_K_M.gguf -ngl 0 -c 2048 -n 80 --temp 0 --no-display-prompt --simple-io --single-turn -p 'Reply with one sentence describing a door.'
} finally {
  [Environment]::SetEnvironmentVariable('LLAMA_ARG_CHAT_TEMPLATE_KWARGS', $FilmPreviousTemplate, 'Process')
}
'The signal came from the other side of the door.' | & .\local-runtime\piper\piper\piper.exe --model .\local-runtime\models\en_US-amy-medium.onnx --output_file .\local-runtime\piper-verify.wav
& .\local-runtime\ffmpeg\ffmpeg-8.0.1-essentials_build\bin\ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 .\local-runtime\piper-verify.wav
```

Expected: unit tests pass; the planner returns a sentence; Piper produces a nonempty WAV with duration greater than zero. These are component checks, not proof of visual or speech quality. If `piper-verify.wav` already exists, choose a new filename; do not overwrite an operator's recording.

## 5. Operation and two end-to-end checks

In the form, enter a brief, exact narration script and style. Optional image references and a music file are local absolute paths; put multiple reference paths on separate lines. Default output is 1080 × 1920 at 24 fps. Other even dimensions from 256 to 3840 and frame rates 24, 25 or 30 are accepted; dimensions and longer jobs other than the tests below are not broadly validated. Duration `0` fits generated narration; a positive target shorter than the narration stops with a clear error instead of truncating speech. The currently installed voice is US English Amy. Music is optional and must be a local file; no music generator is required by the workflow.

`Start job` plans and runs automatically. `Make editable plan only` creates the saved plan without rendering; open the plan editor, edit the JSON, save, then select `Run / resume`. Start a new job to change an already generated narration. A job is saved under `local-film-jobs/<timestamp-id>/`, with `request.json`, `plan.json`, `state.json`, `voices/`, `segments/`, `references/`, logs and `review/`. The `review` directory contains the assembled MP4, segment copies, plan, prompts, settings, generation state, contact sheets and quality report. Completed jobs are never intentionally replaced.

**Small smoke:** submit the brief `A woman hears a signal in a quiet room.`, script `The signal is waiting for us.`, style `hand-drawn anime`, no reference, default size and automatic duration. Expected: state becomes `complete`; review contains an MP4 with audio and a quality report. Inspect the report and play the video.

**Full representative test:** submit brief `A mysterious transmission leads a woman to open an old door.`, script `I taught the machine a word: home. It drew a door. Behind that door was another room, and in that room, another me.`, style `hand-drawn cinematic animation`, a local character reference if available, 1080 × 1920, 24 fps, and target 10 seconds. Expected: at least two 124-frame generation segments, a 10-second assembled MP4 and saved join evidence. If generated narration exceeds the target, the job must stop; increase the duration and resume. Check actual speech, character continuity and the join by playback.

Actual tests on the original machine: a two-segment 10-second reference-guided job completed at 1080 × 1920 using an earlier Qwen 3B planner; after inspection, large-change checks flagged visible clothing/identity drift. A reference-free 6-second anthropomorphic fox job completed at 720 × 1280 after a deliberately too-short five-second request was corrected. A Qwen 4B job completed end to end, and an in-flight worker interruption was resumed using the same ComfyUI prompt ID without a duplicate. Model-generated motion, lip sync, character identity, music quality and the apparent meaning of the scene still require human review.

## 6. Recovery, stops and preservation

The worker records a client-generated ComfyUI prompt ID before submitting and checks queue/history on resume. It waits for an idle queue and GPU memory, serializes its own GPU jobs, and does not cancel other clients. A confirmed GPU out-of-memory error gets at most one automatic retry at a smaller internal generation size; that change is recorded. Unknown submission outcomes stop for inspection instead of blind resubmission. On form-server restart, nonterminal jobs are considered for resume and job locks prevent a second worker from owning the same job. A job that reaches `failed` requires inspection and an explicit `Run / resume`; its logs and state remain available.

- **Model or node mismatch:** run `tools/verify_local_assets.py --hash --fallback`, check the ComfyUI `/object_info` endpoint and `local-film-jobs/comfy-server.log`, and compare revisions with `tools/install_comfy_nodes.py`. Do not replace a modified node directory.
- **Unsupported CUDA/backend:** check the PyTorch version command above and ComfyUI startup log for the CUDA backend and `sol_attn`. Do not silently run without VSA or swap model variants.
- **GPU memory exhaustion or busy GPU:** inspect `nvidia-smi` and `/queue`. The worker waits up to two hours. A retry at reduced internal size is documented; if it fails, stop and ask the operator about resolution or hardware. Stop Strata only if the operator has authorized it and after confirming the correct process.
- **Download failure:** preserve `.part`, `.cache` and existing weights. Re-run a documented resumable downloader only after checking the error. Hash mismatches, rejected licenses, gated models and authentication issues require operator action; never commit tokens.
- **Port conflict:** identify the owner. Pick a free form port with `LOCAL_FILM_PORT`. Port 8191 is currently fixed by the implementation; do not kill an unknown owner or silently point the worker at another ComfyUI.
- **Missing audio or corrupt output:** inspect `review/quality.md`, `quality.json`, segment files, `worker.log` and `state.json`. A completed report is not proof of perceptual lip-sync. Stop rather than mark a bad file successful.
- **Interrupted job:** restart the form server; or run `& $FilmPython -m local_film.pipeline run <absolute-job-directory>`. For a `submitting`/`submitted` prompt missing from both ComfyUI queue and history, stop and inspect output files and ComfyUI logs; the server history may have been lost on restart. Do not fabricate a success or submit a duplicate.
- **Access or permission issues:** verify that the output directory and files inherit read permission for the desktop user. Do not use private temporary directories as the final destination or alter unrelated ACLs.

Stop and ask the operator before accepting a license, choosing a new GPU/runtime/model, overriding a port, replacing an existing checkout, changing another installation, using an unapproved reference/voice/music file, changing an existing job's narration after rendering begins, or deleting any user data. Ask for the actual repository URL if unknown.

For backup, stop the form and wait for the queue to become idle, then copy the repository, `local-film-jobs`, `comfy-local/models`, `comfy-local/input`, `comfy-local/output`, `local-runtime` and any separately stored source media to a verified new backup directory. Git alone does not contain weights, videos, virtual environments or generated jobs. Verify restored hashes with `tools/verify_local_assets.py --hash --fallback` and inspect jobs before running. For updates, back up first, inspect `git status` and the incoming changes, and test a new isolated runtime; do not update the working ComfyUI or nodes in place. To relocate, finish or explicitly stop jobs first and copy the directories; existing job state and staged references store absolute paths, so unfinished jobs cannot be assumed resumable after a move. New jobs can use the new location after setting the environment variables in section 4. To uninstall, first preserve desired outputs and backups, stop only the project's processes, and have the operator explicitly identify any project-local directories to remove. Never remove shared installations, models, or outputs automatically.
