# CPU steering draft

From the TakeFive folder, run the following command with a UTF-8 script.

```powershell
.\Make-Steering-Video.cmd .\examples\dispatch.txt
```

The bundled Qwen planner reads the script on the CPU. Written cuts such as “Cut to Mara” and screenplay headings set the shot boundaries. For continuous prose, the planner works from groups of the author's original sentences. Set the number of shots with `--shots`. When a brief has fewer sentences than requested shots, the planner expands it into coverage. The default duration is five seconds per shot at 24 fps.

```powershell
.\Make-Steering-Video.cmd .\examples\snow.txt --shots 7
```

Open `output\steering\<script-name>\draft.mp4` to watch the edited film. The same folder contains a matching `depth.mp4` and a storyboard. The command prints the path of the saved Blender scene. Each take keeps its exact plan, timeline, timed stills, character visibility measurements and CPU render settings. The picture edit is silent.

Each take also contains `guides.json`. It lists each shot's depth clip, its actual cut length, and the frame and file for every directed pose. A 120-frame shot has 121 frames in its LTX guide. The last frame is duplicated after the cut length to fit the model's temporal grid. The picture edit stays exactly five seconds.

## Directing a revision

The plan contains one record per cast member, one per set, and a list of shots. Characters keep their rig and wardrobe across camera cuts. Interior and exterior sets can share a door ID. Each shot names its location, camera and visible performers. Actor entries select floor marks, movement, facing and timed poses. Frame numbers in the plan start at zero in each shot. Timed directions such as “at frame 40 she nods” can also appear in the script. A pose can include `hold_frames` to keep it through a later beat. Another planner can produce the same JSON and send it straight to the renderer.

Copy the printed plan to `my-edit.json`. For example, change an actor's `end_frame` to change when they reach a mark, or move a pose from frame 60 to 84. A camera can use a framing preset or explicit `position`, `target` and `lens` values. Position and target are in metres in set coordinates. Render the edited plan with the same command.

```powershell
.\Make-Steering-Video.cmd .\my-edit.json --out .\output\steering\revision
```

For hands-on posing, open the take's `stage.blend`. Scrub the timeline to view the camera cuts. The armatures are named after the cast and have editable bones for the head, spine, arms, legs and boots. Save an edited copy, then pass it alongside the matching plan. This path reads the animation directly from Blender. Cut frames and duration should match the plan used for the edit.

```powershell
.\Make-Steering-Video.cmd .\my-edit.json --blend .\my-edited-stage.blend --out .\output\steering\posed
```

The set kit covers offices, radio rooms, a generic interior, streets and snowy exteriors. Its action vocabulary includes walking, passing through doors, sitting, listening, speaking gestures, looking, pointing, leaning and raising a hand. Detailed hand contact and facial performance require further work. Blender uses Cycles on CPU, its CPU compositor, and FFmpeg software H.264 encoding. No image or video model is started by this command.

## Single-shot motion experiment

`shot.py prepare` builds a five-second snow-station walk, a delayed version of the same movement, and matching depth guides. The two versions share their opening and closing poses. The separate GPU commands are `motion` for guide-only takes and `key` for a take with the specified interior stills. These commands run only when explicitly invoked. `--runtime` points them at the installed TakeFive runtime.

To test the actual doorway shot exported with the snow draft, run this from TakeFive.

```powershell
.\runtime\inference-env\Scripts\python.exe .\steering\shot.py all --take .\output\steering\snow\takes\ad8d3cedf1732502 --id shot05
```

The command reads that take's cast, actions, depth footage and existing pose stills. It runs LTX with the original depth, repeats the shot with a 42-frame hold followed by faster movement to the same endpoint, then runs the original movement with up to two interior FLUX-generated stills. The prompt and seed are shared across the three videos. The decoded retimed guide is checked pixel for pixel against the source frames. The resulting `comparison.mp4` plays the takes side by side on the editor's clock. Use `--delay 0` to skip the timing variant.
