# Ref2VA comparison — 2026-10-27

Restore point before testing: `bbb0e3d`. Supplied UI workflow: `E:\minimax\MiniMax-H3-Semantic-Bridge-Fastvideo-Ref2va-updated.json`. The generation graph was flattened for the ComfyUI API; the source file was not edited. Its nested Semantic Bridge node uses first-frame/keyframe image-to-video conditioning despite the Ref2VA model selection; this is not a test of ComfyUI's native `MiniMaxH3ReferenceToVideo` multi-reference node.

## Setup

- ComfyUI 0.38.0 from `E:\SwarmUI\dlbackend\comfy\ComfyUI`, isolated base `F:\film-pipeline\comfy-local`, RTX 4060 Ti 16,380 MiB, driver 591.86, 128 GiB RAM, low VRAM mode.
- Installed a separate project-local PyTorch 2.11.0+cu130 runtime; the original ComfyUI environment was not modified. ComfyUI's cu128 runtime disabled the CUDA backend needed by Sol-Attn. `nvidia-vfx` 0.2.0.0 installed in project-local python-extra.
- Nodes: KJNodes `2371136d2fa6fd0914e514cd99b36dabe5db9adf`; Ref2VA-VSA `323a0a5f7c636cc70f95464145732f81f04a72e9`; Memory Cleanup `58de13a6090e04408e343501ff8902c034d9f518`; VideoHelperSuite `4d907bee61e92c2e65af3bd6383a4e4d356126d1`; Nvidia VFX `38d790ded00650681fa3645362efe28c8560cf40`; LC AV nodes `032d77c7ced1873a28bbc4869c5ba81c42172f90`; Semantic Bridge v1.0 archive and v1 adapter.
- Source-selected Ref2VA base `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (20,970,379,616 bytes), `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors`, `fasth3_vsa_gate.safetensors`, `MiniMaxH3_SemanticBridge_v1.safetensors`. Shared `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, video fp16 and audio fp32 VAEs.

## Controlled comparison

Both used `minimax-test-anime.png`, the same original pocket-watch prompt, seed 2801, 704x1280, 124 frames, 24 fps, 5.167 seconds. This 11:20 image is close to, but not exactly, a 9:16 Instagram Reel. No final Reel crop or resize was applied.

- Existing FL2VA baseline: `baseline-fl2va-eight-step.mp4`; FP8 pruned FL2VA, FL2V 8-step turbo, `res_multistep`, `simple`, video/audio shifts 12/3. Approx. 720 seconds from recorded submission to file timestamp; generated earlier under cu128, so timing is not a controlled runtime benchmark.
- Supplied generation path: `supplied_00001-audio.mp4`; Ref2VA INT8, Ref2V 4-step turbo, `er_sde`, `sgm_uniform`, shifts 6/3, bridge alpha 0.15 per-token, VSA sparsity 0.75. ComfyUI reported 267.53 seconds; sampled peak GPU memory 15,589 MiB (includes other GPU activity). The system-wide RAM cleanup options were disabled to avoid manipulating other applications. The RGThree UI muter and RTX upscaling branch were omitted for the raw, same-resolution test.
- Separate 2x RTX VFX ULTRA test on the encoded raw output: `supplied-upscaled_00001-audio.mp4`, 1408x2560, reported 17.32 seconds. This checks the supplied upscaling node but is not the original uncompressed connection; it may include re-encoding differences.
- Sampled contact sheets show the supplied result maintains the anime character and watch, shows hand/head movement, and introduces a pronounced camera push-in despite a static-camera instruction. The existing baseline stays wider and also moves the hands and head. Sampled frames alone do not establish temporal smoothness or a general quality winner.

## Audio-driven variant

`supplied-audio-sync_00001-audio.mp4` retains the approved `LCH3AudioSync` node and same 5.17 s duration; it uses the existing approved speech prompt and `minimax-01-narration.wav`, the first 5.17 seconds of the 9.97 s input. ComfyUI reported 246.50 seconds with cached model nodes; sampled GPU peak 15,567 MiB. 32 kHz mono waveform correlation with the source was 0.99724 after AAC encoding (existing FL2VA approved audio baseline 0.99751). This verifies output audio content, not phoneme-level synchronization or perceptual lip-sync quality. Sampled images show several distinct mouth poses. Human playback review is needed. The approved FL2VA path remains available unchanged.

First attempt under the existing runtime hit a Windows console encoding exception in the cleanup node, killing its worker. Launcher now configures UTF-8 before loading ComfyUI. No original reels or source installations were overwritten. Result and submitted API graphs are alongside this report in `comfy-local`.
