# Experimental LatentSync moving-character test

`latentsync_lipsync.py` is a local research experiment. The default InsightFace `buffalo_l` detector model weights are **licensed for non-commercial research only**; the code requires `--research-only` to acknowledge that condition. The [InsightFace package documentation](https://pypi.org/project/insightface/0.7.3/) distinguishes the MIT-licensed library from its restricted pretrained models. LatentSync's [1.5 model card](https://huggingface.co/ByteDance/LatentSync-1.5) identifies its model license as OpenRAIL++; review all model terms separately before any intended use.

Run from the project root using the MuseTalk environment, which supplies the CPU DWPose tracker. The isolated LatentSync environment runs generation on the GPU. The project needs FFmpeg and FFprobe on PATH, DWPose files under `tools/MuseTalk`, and the prepared `venvs/latentsync`, `tools/LatentSync/checkpoints` and `venvs/hf-cache` directories. The code does not download models while running.

```powershell
& .\venvs\musetalk\Scripts\python.exe .\tools\latentsync_lipsync.py `
  --video .\video\full_motion\anime-quality.mp4 `
  --audio .\audio\lipsync\character.wav `
  --face-crop 128,24,448,448 `
  --out .\video\full_motion\anime-latentsync-research.mp4 `
  --research-only
```

The crop is `x,y,width,height` in source-video pixels and must be square, inside the frame, and large enough to contain the face throughout the shot. The example coordinates were visually checked for this specific anime clip; choose and review a crop for each other shot. Tracking fails on weak, missing, or suddenly jumping landmarks; InsightFace can also fail on stylized faces. Failures are reported and existing outputs are preserved unless `--overwrite` is given and the replacement has completed and passed checks.

The tool converts speech to mono 16 kHz, verifies that the source motion is at least as long as the speech, and normalizes the source to 25 fps without looping. It keeps the full speech and requires enough real source frames to cover its final partial frame; it fails if that frame cannot be decoded. DWPose checks every frame on CPU. Then it uses independently generated chunks of six seconds by default (`--chunk-seconds` accepts 1–12) to bound GPU memory, strips LatentSync's surplus tail frames, and composites a feathered tracked-mouth region into the original moving frame. Chunk boundaries may introduce visual or lip-sync discontinuities and need review. The output preserves the source dimensions; it is not automatically sized for Reels.

The original single-shot prototype passed one anime crop. The reusable chunked implementation also completed a real 210-frame, two-chunk test on the 3D mirror shot with `--face-crop 128,130,448,448`; the 25 fps output and speech timeline were checked, and selected face frames were inspected. That run used the earlier floor-to-frame behavior. The subsequent full-speech change completed a 201-frame GPU run with the experimental DWPose mode described below. Four CPU tests include simulated multi-chunk generation and an import check against the installed engine. Neither phoneme accuracy nor subjective visual or audio quality is certified. Inspect the finished video and listen to its speech, especially at every chunk boundary, before use. Each run keeps a LatentSync log in `logs/` and uses a private temporary working directory to avoid the upstream engine's fixed `temp` deletion affecting other runs.

## Experimental alternative to the InsightFace weights

The opt-in `--detector dwpose` mode uses the tracked DWPose 68-point face landmarks to approximate LatentSync's two eyebrow centers and nose center. It calls LatentSync's original affine warp and restoration code and does **not load InsightFace buffalo_l weights**. The upstream Python module still imports the MIT-licensed InsightFace library, which must remain installed; the restricted pretrained detector weights are not copied or invoked for this mode. The original InsightFace mode remains the default and continues to require `--research-only`.

The installed `dw-ll_ucoco_384.pth` SHA-256 is `0d9408b13cd863c4e95a149dd31232f88f2a12aa6cf8964ed74d7d97748c7a07`, matching the [yzd-v/DWPose model repository](https://huggingface.co/yzd-v/DWPose), which labels the model Apache-2.0. LatentSync 1.5, the VAE, Whisper, training data, other dependencies and distribution may have separate terms; this is not a commercial-use clearance.

Six sampled anime and 3D frames were compared against the InsightFace anchors on CPU. The resulting native affine crops were visually similar, and six selected points differed by an average of 3.49 pixels (maximum 7.92) in the native alignment canvas. This is a small, selected sample, not an accuracy guarantee. The bridge's mapping, frame-count guard and real CPU affine warp pass tests. One real two-chunk run with `--detector dwpose` completed on the hand-drawn 02 retry: `jobs/handdrawn-dwpose-latentsync.mp4` contains 201 frames at 25 fps and the full 8.014-second narration. Selected face and chunk-boundary frames were inspected in `jobs/handdrawn-dwpose-faces.jpg`, and audio timing was measured. Other faces, head turns, animation styles and occlusions can fail or produce misleading landmarks; this single test does not establish phoneme accuracy, natural motion, sound quality or broader reliability. A human should watch and listen before use.

To try the bridge as an experiment, replace `--research-only` in the command above with `--detector dwpose`. It still needs the locally prepared LatentSync and DWPose environments and model files, and it still requires review of the output and all applicable licenses.

## Separate model and media terms

The detector change does not settle the terms of the whole reel. The sources below describe the individual components used in this batch; eligibility, acceptance, notices, the specific installed conversions and source media need their own review:

| Component | Published model or code terms |
| --- | --- |
| Original InsightFace `buffalo_l` detector weights | [Non-commercial research only](https://pypi.org/project/insightface/0.7.3/). The separate library code is MIT. The existing 03 draft used these weights. |
| DWPose 68-point model | [Apache-2.0 model tag](https://huggingface.co/yzd-v/DWPose); local checkpoint hash matches the published `.pth`. |
| LatentSync 1.5 model | [OpenRAIL++ model tag](https://huggingface.co/ByteDance/LatentSync-1.5); [source code is Apache-2.0](https://github.com/bytedance/LatentSync/blob/main/LICENSE). |
| Stable Diffusion VAE | [MIT model tag](https://huggingface.co/stabilityai/sd-vae-ft-mse). |
| Whisper tiny | [Whisper source MIT](https://github.com/openai/whisper/blob/main/LICENSE); local `tiny.pt` hash matches OpenAI's official tiny checkpoint URL. |
| FLUX.2 klein 4B source portraits | [Apache-2.0 model](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B). |
| WAN 2.2 TI2V 5B motion | [Apache-2.0 model](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B). |
| Kokoro narration | The local generation log identifies `audio-cpp/audio.cpp-gguf/Kokoro-82M-GGUF`; the [conversion repository lists Apache-2.0](https://huggingface.co/audio-cpp/audio.cpp-gguf), as does the [original model](https://huggingface.co/hexgrad/Kokoro-82M). Check the specific voice and conversion's provenance separately. |
| Ambient music | `audio/reels/sfx/README.md` identifies a Stable Audio 3 Small Music sample. The [model card](https://huggingface.co/stabilityai/stable-audio-3-small-music) names the Stability AI Community License and Gemma terms. [Stability's self-hosting guidance](https://kb.stability.ai/knowledge-base/stable-audio-commerical-and-usage-licensing) describes commercial registration and revenue conditions; determine which terms apply to the user's situation. |

This inventory is a starting point, not legal clearance or a statement that every source, transformation, dataset, distribution or use has been reviewed.
