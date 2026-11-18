# TakeFive

## Make a film from your own text

Drag a plain English UTF-8 `.txt` story onto **Make-Film.cmd**, or double-click it and paste a paragraph. Give characters distinct names and put exact spoken lines in double quotation marks. A silent story works too. From PowerShell you can run the snow example like this.

```powershell
.\Make-Film.cmd .\examples\snow.txt
```

The local Qwen planner casts the film and chooses the camera setups. Piper synthesizes the lines. FLUX generates the cast photographs, sets and opening frames from scratch. MiniMax H3 animates each shot with its own dry voice guide. The editor cuts those shots over one continuous soundtrack, including offscreen speech. Each stage runs automatically on this installation. Once the models are installed, the render uses the local machine and loopback ComfyUI.

Find the finished `film.mp4` and contact sheet in the folder printed by the launcher under `output\text-films`. The exact story, shot directions, voices, timings, generated references and take decisions are saved alongside them. A second launch verifies and reuses the completed MP4. An interrupted render can reuse completed images and video takes.

The default is five shots for a short brief. More quoted turns can increase that count. You can set a global seed, shot count and visual style.

```powershell
.\Make-Film.cmd "D:\Stories\Last ferry.txt" --seed 17 --shots 6 --style "Grainy 1970s color film under overcast light"
```

This version supports 1–16 shots, up to one new speaking turn per shot, and two bundled English voices. Most requested takes last five seconds. A long line can extend its shot. An across-cut delivery can continue into the next picture. A fixed local check can order one extra take for a black picture, a freeze or a possible internal cut. Character identity, the meaning of an action and the accuracy of lip movement still need to be judged by watching the result.

## Directed reference films

The dispatch-office and earlier snow productions used individually prepared shot directions and references. Their launchers replay those productions.

**[Watch the 28-second LTX film](films/dispatch-office.mp4)** · [Five-shot contact sheet](films/dispatch-office-board.jpg) · [Blender staging draft](films/office/film.mp4) · [Source paragraph](examples/dispatch.txt) · [Editable Blender scene](films/office/scene.blend)

**[Watch the 28-second MiniMax H3 film](films/dispatch-office-h3.mp4)** · [H3 contact sheet](films/dispatch-office-h3-board.jpg) · [H3 shot directions](generation/h3-office.json)

[Seven-shot snow screenplay](films/signal-in-the-snow/scene.json) · [Directed snow launcher](Generate-Snow.cmd)

To reproduce either cut, see the local generation instructions for CPU preparation and GPU rendering. [LTX workflow](generation/README.md) · [MiniMax H3 workflow](generation/README.md#generate-the-minimax-h3-version)

## Render the original Blender scene

For the original dispatch-office staging, run this command from PowerShell in the TakeFive folder. The `Render.cmd` text-file shortcut now uses the same filmmaker as `Make-Film.cmd`.

```powershell
python film.py render examples\dispatch.txt --reuse films\office --out output
```

Write one employee arriving, speaking with a seated manager, then leaving. Give each character one quoted speaking turn, employee first. You can change why they meet, their lines, their names, wardrobe and door color. If you omit the lines, the local planner drafts them. The renderer currently provides one set, two character rigs and five camera setups. A different location, third character or new action needs additional staging in Blender.

Completed renders print the path to the MP4 and keep the edit in a versioned output folder. For an independent render from the paragraph, omit `--reuse` and add `--fresh` to redraw all five shots. For an exact replay of a particular performance, use the saved bundle.

## What happens at the cuts

| Time in the sample | Picture | Sound and performance |
| --- | --- | --- |
| 0–5 s | Eli enters through the blue depot door. Mara is behind the desk. | Footsteps and indoor room tone. |
| 5–10 s | Close on Eli. | He asks where to send a waiting driver. |
| 10–18 s | Cut to Mara listening, then replying. | The last 0.95 seconds of Eli's question play over her reaction. After a 0.55-second beat, her mouth follows her reply. |
| 18–23 s | The wide shot returns. Eli turns and leaves. | Mara stays seated as Eli heads through the same door. |
| 23–28 s | Exterior. Eli is already walking away. | His walk cycle continues across the cut as indoor sound gives way to the street. |

The Blender scene contains both sides of the doorway, one instance of each character and five camera markers. The actors have a continuous 24 fps timeline. A camera cut changes the view while the same performance and 48 kHz sound mix continue.

## Direct a revision

Edit a copy of the source paragraph or copy `films\office\scene.json` to `my-scene.json` and change exact values. Then render against the take you want to revise.

```powershell
Copy-Item films\office\scene.json my-scene.json
# Edit my-scene.json in your text editor, then run
python film.py render my-scene.json --reuse films\office --out output
```

| Control | Effect |
| --- | --- |
| `cast.employee` and `cast.manager` | Each entry holds the name, spoken line, voice model and coat color. For an extra Piper voice, put its ONNX and companion JSON in `runtime\voices`. |
| `door` and `coat` | Choose rust, teal, navy, olive, ochre, plum, blue or cream. |
| `shots[].lens` and `shots[].seconds` | Set lens focal length in millimeters and minimum shot duration in seconds. Longer lines extend the speaking shots automatically. |
| `bridge` and `reply_beat` | Set how much of the employee's line carries onto the manager's shot and the pause before her reply, in seconds. Very short questions use a proportionally shorter bridge. |
| `exit_crossing` | Set where the employee crosses the threshold, as a fraction of the departure shot. |
| `--width` | Change the output resolution. The default width of 1280 gives a 1280 × 720 picture. |

The [Bay five revision](films/bay-five/film.mp4) changes a single word in the paragraph. Only the manager's voice and picture take changed. Both versions include the original prose, scene directions, animated Blender file, individual camera clips, first/middle/last frames, voice recordings, mouth cues, timing and mixed audio.

## Replay the edit or replace a take

```powershell
python film.py assemble films\office output\replay.mp4
```

This uses the five saved camera clips and `mix.wav`. On the tested FFmpeg installation the rebuilt MP4 was byte-identical to the original. Use this operation to preserve the exact take, including each speaker's delivery. Regenerating speech or rerendering on different graphics drivers can change the result.

To use a hand-edited or locally generated picture, put one or more MP4s named `arrival`, `employee`, `manager`, `departure` or `street` in a folder. Each must cover at least its shot's duration. For example, with a replacement `takes\manager.mp4` run

```powershell
python film.py finish films\office --takes takes --out output\finished
```

The editor conforms the replacement to the saved framing and frame rate, checks the length, then lays it under the original sound mix. Point `--reuse` at this finished bundle to retain an approved replacement while revising other shots. `employee-camera.wav` and `manager-camera.wav` contain only the on-camera speaker for that shot. The manager's file starts with silence while the employee finishes his question off camera.

## Local requirements

The supplied runtime includes the Qwen2.5-3B-Instruct GGUF planner and CPU llama.cpp runner, Piper with the Ryan and Kristin voices, and Rhubarb with its English recognition data. No account, network access or background model server is needed for the animated film. The runtime is approximately 2.4 GB. Its files travel with the project.

The verified Windows setup used Python 3.13.15, NumPy 2.5.4, Pillow 13.0.0, Blender 5.2.2 and FFmpeg/FFprobe 8.0.1. The command uses the system Blender and FFmpeg. Install the Python packages in `requirements.txt` if using a new Python environment. `TAKEFIVE_BLENDER`, `TAKEFIVE_FFMPEG` and `TAKEFIVE_FFPROBE` can point to specific executables. `TAKEFIVE_WORK` can point to a different writable cache folder. If restoring a copy that lacks the bundled runtime, `python setup_runtime.py --help` lists the local tool directories and model files to supply.

The text planner, voice models and lip analysis come from their respective upstream projects. Their published model cards and license terms apply to their files. [Qwen](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) · [llama.cpp](https://github.com/ggml-org/llama.cpp) · [Piper](https://github.com/rhasspy/piper) · [Ryan voice](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/ryan/medium) · [Kristin voice](https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/kristin/medium) · [Rhubarb](https://github.com/DanielSWolf/rhubarb-lip-sync)

## Model-generated footage

The project includes a local FLUX.2 klein and LTX-2.3 FP8 generation workflow for the same five shots. CPU preparation builds the control videos, speech tracks, shot prompts and ComfyUI graphs. An explicit render generates the reference images and motion and puts the result into the existing sound edit. Start with the manager's reply when the GPU is free. [Generation instructions](generation/README.md) · [GPU launcher](Generate-Realistic.cmd)
