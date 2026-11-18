# Generate the realistic cut

The local renderer uses FLUX.2 klein for actor and location reference images and LTX-2.3 Distilled FP8 for motion. It builds a private ComfyUI process from the copy in `runtime\comfyui`. Its Python environment and all six model files live inside TakeFive. Generation uses the saved dialogue, a realistic first frame and an edge guide made from each moving Blender shot. The final mix comes from the original cut. [Video checkpoint](https://huggingface.co/Lightricks/LTX-2.3-fp8) · [Motion adapter](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control) · [Appearance model](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8)

## While the GPU is occupied

These commands use CPU, disk and software video codecs. Run them from the project root.

```powershell
python -B generation\realistic.py prepare
python -B generation\realistic.py check --hash-models --cpu-smoke
```

The first command prepares five raw motion guides, five edge guides, five starting images and five isolated stereo WAV files. Each 5-second shot occupies 120 frames in the edit and gets 121 frames for LTX. The 8-second manager shot gets 193 frames for an edit of 192. Her isolated recording begins with 1.5 seconds of silence while Eli's question continues on the master mix.

The check verifies every media checksum and model header, and validates each generation graph in ComfyUI's CPU mode. `--hash-models` also checks the six published SHA-256 digests. `--cpu-smoke` sends one existing still through a CPU-only local video export. It also uses the five staged motion guides in a temporary edit to verify that takes can be saved, reopened, trimmed and assembled with the identical decoded soundtrack. The command prints the location of the readiness report. The generated API graph JSONs and all shot inputs are beside it.

## Once the GPU is available

Double-click [Generate-Realistic.cmd](../Generate-Realistic.cmd) for the manager's shot. From PowerShell the commands are

```powershell
python -B generation\realistic.py render --shot manager
python -B generation\realistic.py render --shot all
```

The first command generates Mara's reference portrait, then an eight-second LTX take. It prints the path to a 28-second review MP4 with that take cut into the office scene. The second command produces the remaining shots and the full model-generated edit. The renderer reuses completed pictures and cast reference images for the same inputs. Nothing is scheduled automatically.

To review an appearance before spending time on its video, run `python -B generation\realistic.py looks --shot manager`. For a different performance, pass `--bundle` pointing to its finished TakeFive bundle. To direct a new treatment, edit a copy of [office.json](office.json) and pass `--direction your-file.json`. It controls the cast descriptions, room, shot prompts, seed, guide strength, frame size and sampling steps. A changed treatment creates a new input package. Earlier takes remain available.

The `opening_frames` entries set each camera's framing, actor positions and reference pictures. The wide shots use small face crops from the dialogue portraits so the reference pictures do not bring extra people into the room. Each `reference_crops` rectangle gives its left edge, top edge, width and height as fractions of the source picture. For the entrance, `source_start_frame` starts the guide with Eli visible in the doorway and retimes the remaining walk to the five-second edit.

[office.framing.json](office.framing.json) tightens Mara's reverse angle around her face and the blinds. On Eli's locked close-up the edit holds the door from the first frame while preserving his moving face and body inside the specified outline. This outline is bound to the checksum of his approved take. Changing an edit reuses the same performances and soundtrack. A custom direction file can have its own matching `.framing.json` companion.

Review Mara's face, glasses and lips while Eli finishes offscreen, her first spoken syllable, and whether Eli still looks like the same person when the camera goes outside. The CPU readiness report covers wiring, assets, audio and timing. Peak VRAM, render speed and visual continuity require a GPU render.

## Restore the local runtime

The prepared installation already includes the engine and models. On another Windows x64 PC, Python 3.13 and `uv` can restore them from these files. The installer pins the ComfyUI source revision and CUDA-enabled PyTorch wheels. The model fetcher resumes incomplete transfers and checks each SHA-256 against [models.json](models.json). Initial downloads require internet access. Inference runs offline.

```powershell
python generation\setup_engine.py
python generation\fetch_models.py
```

The existing `film.py neural` entry point targets the separately licensed LTX-2.5 Layout to Render workflow. That version requires account access to both publisher repositories and its native Python pipeline. The prepared LTX-2.3 workflow above uses the public Union Control adapter. [2.5 model](https://huggingface.co/Lightricks/LTX-2.5) · [2.5 Layout to Render adapter](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Layout-To-Render)

## Generate the MiniMax H3 version

Run the launcher in the TakeFive folder. With a shot name it renders that take. With no argument it renders all five and prints the path to the finished MP4.

```powershell
.\Generate-H3.cmd arrival
.\Generate-H3.cmd
```

The H3 renderer reads the approved FLUX photographs in `films/dispatch-looks`. It takes a portrait crop for each actor and places the shot's photograph at frame zero. The walking shots use that single photographic anchor. The dialogue shots reuse their photograph before the first word to hold the listening pose. Eli and Mara each get their own 48 kHz recording during generation, including their listening pauses. The edit uses the original continuous mix so Eli can finish his question across the cut to Mara.

To direct a retake, change the individual shot's prompt, seed, cast order, or opening crop. The optional `photo_frames` list places the shot photograph at specific frame numbers. Its default is `[0]`. An empty list generates from the portraits and prompt alone. A five-second edit uses 120 of 124 generated frames. The eight-second edit uses all 192. Unchanged takes are reused, and the renderer saves the exact graph, input hashes, and accepted picture for each shot. [H3 shot directions](h3-office.json)

Mara's approved H3 take changes camera position at frame 34. The edit starts with a silent reaction from later in her own take and blends back to her speaking performance over three frames. The original 192-frame slot and the recorded reply keep their timing. The edit is attached to this take's checksum so a future retake can be reviewed independently. [H3 edit settings](h3-office.framing.json)

```powershell
.\runtime\inference-env\Scripts\python.exe -B generation\h3.py prepare
.\runtime\inference-env\Scripts\python.exe -B generation\h3.py render --direction path\to\my-h3-direction.json
```

The standalone installation uses the INT8 ConvRot Ref2VA checkpoint, four-step Turbo LoRA, VSA gate, semantic bridge, Qwen3VL text encoder and both H3 VAEs. It runs on a private loopback ComfyUI instance. To restore the H3 assets from a local library with matching `models` and `custom_nodes` folders, run the following after installing the shared engine. The installer verifies the weights and node source against pinned SHA-256 digests.

```powershell
.\runtime\inference-env\Scripts\python.exe -B generation\setup_h3.py F:\path\to\comfy-local
```

## Signal in the Snow

This 38-second H3 film follows a seven-shot screenplay. Kate hears her own warning on the radio. Three knocks draw James to the door. The cut from his hand on the latch to an empty snowy threshold is his disappearance. The final take returns to Kate at the microphone.

Run `.\Generate-Snow.cmd` for the complete edit or `.\Generate-Snow.cmd doorLatch` for a single take. Each shot has its own direction, seed, and photographic starting frame. The prepared audio includes the original Piper performances and three knocks. Kate's opening and closing warnings share one voice recording. [Shot directions](h3-snow.json) · [Screenplay](../films/signal-in-the-snow/scene.json) · [Photographic starting frames](../films/signal-in-the-snow/looks)

To change a camera setup, edit its opening-frame recipe and run the two commands below. The radio and James starting photos are the original approved references. The other five are local FLUX.2 klein generations. All seven H3 takes use the same local renderer as the dispatch film. [Opening-frame recipe](../films/signal-in-the-snow/opening-frames.json)

```powershell
.\runtime\inference-env\Scripts\python.exe -B generation\opening_frames.py films\signal-in-the-snow
.\Generate-Snow.cmd
```
