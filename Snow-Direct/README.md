# Snow

A 35-second Blender animatic of the polar station radio story. Open `Snow.blend`, select camera view with Numpad 0 if needed, and scrub frames 1–840 at 24 fps. `Snow.mp4` is the watch copy. The original text is in [screenplay.txt](screenplay.txt). [Shot index](Shots.jpg)

## What went into the scene

I authored the staging, camera positions, timing, poses, contact targets, footsteps, clothing, set, lighting and mechanical animation directly in Blender Python. The build starts with an empty Blender file. The cast consists of two blank, skinned Quaternius figures with individual finger bones and two separate hairstyles. I used their geometry, skeletons, skin textures, eyebrows, eyes and hair. I made the jackets, assigned the other wardrobe materials, and built the station furniture, radio and airlock for this scene. The two characters have one persistent location and skeleton each across all seven cameras.

Quaternius released the Universal Base Characters under CC0. The bundle includes the license, the four derived local GLBs and the download manifest with exact upstream file URLs, SHA-256 hashes, and source revision. The GLBs carry the rest rigs. All performance keys come from this scene's source. [Creator’s asset page](https://quaternius.com/packs/universalbasecharacters.html) · [License](assets/QUATERNIUS-LICENSE.txt) · [Asset manifest](assets/sources.json)

I reused two project inputs so the comparison follows the same story and sound cues. `TakeFive/examples/snow.txt` supplies the screenplay. `TakeFive/output/openrouter/seedance-mini-480p-one-pass/sound/master.wav` supplies the prior 48 kHz mono radio play, including the synthesized voices, radio processing, knocks and wind. Their copies here are sufficient to rebuild. I did not use a previous Blender file, motion clip, action library, planning model or generative video service to make the pictures.

## Shot decisions

| Frames | Camera | Performance and staging |
| --- | --- | --- |
| 1–120 | Reception | Establish Kate seated at the western edge of the radio bench, James on the floor to her right, and the closed hatch farther right. Kate's attention lifts as her voice comes over the receiver. |
| 121–240 | My voice | Come close to Kate from the working side of the room. She lifts her head, glances toward James and makes a small gesture as she recognizes the voice. |
| 241–360 | Three knocks | Hold on the closed hatch. A hanging brass inspection tag jumps on each knock while the lever stays at rest. |
| 361–480 | Someone outside | James looks back, delivers the line and pivots toward the door. The camera follows as he takes his first steps. |
| 481–600 | His hand on the latch | Pick up the same walk. He reaches, hesitates just short of the handle, touches it, depresses it and draws the door toward himself. His outside step makes room for the swinging leaf. |
| 601–720 | An empty threshold | Return to the wide view with the door still open to whiteout. James disappears across the cut. Kate turns in her chair and searches the opening. |
| 721–840 | Transmit | Stay close to the desk as Kate leans forward, operates the talk switch and speaks the warning heard at the beginning. |

The pause before contact and the disappearance across a cut are directorial interpretations of the original paragraph. The seven shots share a single 35-second audio track. Dialogue drives a small amplitude-based jaw shape. The scene supplies timing and body acting, with simplified mouth articulation.

## Checks on the saved Blender scene

I reopened the saved file and sampled the deformed body meshes, the triangulated lever and the talk switch. Distances below come from evaluated geometry in metres converted to millimetres. The result documents one directly authored screenplay. New story events still need new staging and acting decisions. [Measurements](measurements.json) · [Verification source](source/check_scene.py)

| Event | Observed result |
| --- | --- |
| Walk across the cut | James advances 20.1 mm in the frame before the cut, 19.0 mm across it and 18.9 mm in the next frame. Four checked foot plants drift under 0.02 mm. The first right plant drifts 8.1 mm. |
| Hover at frames 500–512 | The nearest glove vertex stays 25.38–25.40 mm from the lever, across all 13 frames. |
| Reach and pull | The registered fingertip is 0.003 mm from the lever at frame 522. The lever depresses before the hinge moves. The fingertip stays within 0.38 mm of the lever through frame 571 as it wraps from the near to the far side and the door swings through 50°. |
| Contact approximation | The glove uses keyframed deformation. Its deepest sampled mesh overlap is 8.0 mm during the finger curl at frame 531 and about 3.2 mm in the held grip. |
| Chair and disappearance | Kate’s rig stays on the same chair mark. The seated pelvis joint is 107.3 mm above the seat surface at all six sampled frames. James is visible at 600 and gone at 601. Kate remains visible. |
| Push to talk | Kate’s registered fingertip stays within 0.02 mm of the depressed key at the four sampled frames from 747 through 817. |

I inspected native camera renders for each shot, including the lift of Kate’s face from the radio, James's planted walk, the sideways view of the gap and hooked fingers, the empty doorway, and Kate pressing the button with the microphone in frame. Two close frames are included for shot 5 in the shot index. [Shot index](Shots.jpg)

The delivered MP4 decoded to 840 frames and exactly 35.000 seconds of picture and sound. Eight sampled frames in the native render cache matched the reviewed previews pixel for pixel. After H.264 encoding, their mean absolute channel difference was 1.62–2.01 out of 255. The decoded audio and source WAV had a zero-lag waveform correlation of at least 0.998 in every five-second segment. The MP4 SHA-256 is `66659ef0ded4ad4d59295f10df82407d263e680331d5c1f022e52f42238bbc4e`.

## Editing

Enable viewport overlays to see the skeletons and controls. The Outliner separates the stage, controls for each character, cast meshes and cameras. Select an actor’s `arm r • goal` or `arm l • goal` to edit a wrist. The companion `bend` control directs the elbow. The leg controls work the same way. The camera markers live on the master timeline. The `LATCH` control rotates in local Y and the `AIRLOCK` control rotates in local Z.

For a repeatable revision, change the source coordinates and rebuild. [performance.py](source/performance.py) contains Kate’s and James’s individually authored beats, James’s left and right footprints and the prop timing. The touch targets there are transformed from the actual moving lever into world space. [cast.py](source/cast.py) constructs and dresses the rigs and registers the fingertip. [stage_art.py](source/stage_art.py) contains the room and prop dimensions in metres. [build_scene.py](source/build_scene.py) assembles them, adds the cameras and sound and saves the Blender file.

For example, to audition a 5 cm hesitation, change the two values of `0.0254` in `GAP_KEYS` at frames 500 and 512 to `0.05`. Frame 522 still brings the glove to the handle. To change just what the audience sees, edit the position, aim or focal length of `His hand on the latch` in `cameras()`. Both edits preserve the shared timeline and audio cue.

## Reproduce locally

Run these PowerShell commands from this directory using Blender 5.2.2 LTS, Python 3.11 or later and FFmpeg. The supplied assets make the build offline. The render script uses Blender Cycles on CPU and can resume completed image frames. It selects the frame cache by the content hash of the Blender file, so edits automatically get a fresh render.

```powershell
$blender = 'F:\ue\Blender 5.2\blender.exe'
$env:BLENDER_USER_RESOURCES = Join-Path $PWD 'work\blender'
& $blender -b -noaudio --factory-startup -t 12 --python-exit-code 3 -P .\source\build_scene.py
& $blender -b .\Snow.blend -noaudio -t 12 --python-exit-code 3 -P .\source\check_scene.py
python .\source\render.py --blender $blender
python -B .\source\check_movie.py
```

The build replaces this directory’s generated `Snow.blend`. The render writes PNGs under `work` and muxes the supplied WAV into `Snow.mp4`. The tools used here were Blender 5.2.2 LTS (build `d13f752e3b9c`), CPython 3.13.15, FFmpeg/ffprobe 8.0.1 and Pillow 13.0.0 for the optional shot index. Rendering used CPU Cycles, four samples and denoising, at 704 × 396. The movie is H.264 with AAC sound. The Blender file also contains the soundtrack and its image textures.

[prepare_assets.py](source/prepare_assets.py) records the GLB derivation and the two local copies. [inspect_grasp.py](source/inspect_grasp.py) probes alternative finger angles on a held frame in memory. [render.py](source/render.py) renders and assembles the film. [contact_sheet.py](source/contact_sheet.py) makes the shot index from native images. [check_movie.py](source/check_movie.py) counts decoded frames, compares eight pictures to their Blender originals and compares the decoded audio to the radio play in seven five-second windows. The shot index and picture comparison use Pillow.
