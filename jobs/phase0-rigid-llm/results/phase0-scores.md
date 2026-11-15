# Phase 0 scores — measured on file-cabinet, 2026-11-15. Do not invent numbers.

## Lane A — P0-A1 "Kate: the signal is holding" (keyframe image-to-video)

- Render command: `tools\minimax_speech.py submit --name phase0-a1-kate-radio --image series\characters\kate\portrait.png --audio jobs\phase0-rigid-llm\audio\p0-a1-kate-radio.wav --frames 141 --width 704 --height 1280 --seed 2801`
- Take name: phase0-a1-kate-radio
- Output file: `comfy-local\output\minimax-speech\phase0-a1-kate-radio_00001_.mp4` (2,238,789 bytes)
- Prompt ID: 11215c83-6c7b-4374-9602-ddeaaed2a23b. Submitted 02:28:58 CST, success ~02:42:16 CST.
- Render time (submit to finished): 13 min 16 s (ComfyUI log: "Prompt executed in 00:13:16").
  Cold model load ~95 s init + 8 sampler steps x ~86 s/step + VAE decode/save. First H3 run after
  server start; a warm rerun would be shorter. Prior repo evidence said ~5 min per 124-frame
  generation — this 141-frame cold run was 2.6x that. Budget 10-15 min/shot until warm timings are measured.
- Human minutes (hands-on, excluding render wait): ~20 min (draft + Piper TTS + submit + polls).
  Includes ~5 min lost to a dead ComfyUI (Start-Process child killed on SSH disconnect; rerun
  in a persistent session fixed it — see phase0-plan.md note) and a stale state file from the
  failed first submit (deleted, it had no prompt_id).
- Duration / resolution / fps (ffprobe): 5.875 s, 704x1280, 24 fps, 141 frames, h264 + AAC audio.
- Motion survival: PARTIAL — the intended action does happen, but not as one continuous shot.
  The clip has two phases: t=0-~2.8 s tight portrait against a plain wall (Kate speaking, mouth
  moving, eyes blinking), then a hard cut at ~t=2.8-3.5 s to the desk scene (snow window, lamp,
  radio, both hands on the dial). In the desk phase Kate turns her head toward the radio in
  profile by t=5 s — the prompted head turn DID survive, and the hands-on-dial DID survive.
  But the "static camera medium close-up at the radio desk" was not the shot for the first half:
  the first frame (bare portrait) anchored the model in portrait-land and the prompt's desk
  scene only arrived late. The static camera held within each phase (no drift).
- Character consistency: EXCELLENT. Same Kate in every frame and across the scene jump — face,
  silver-streaked brown hair, navy jacket, cream sweater, lanyard with brass ring all preserved.
- Lip sync: 4/5 by visual inspection. Mouth opens/closes in step with the speech envelope
  (closed at the t=2.0 s pause after "James.", open at t=2.67 s on "Whatever..."). Output audio
  is the input Piper line passed through the H3 audio VAE: envelope correlation 0.992, best lag
  0 ms, same RMS (0.167 in / 0.165 out). Audio timing is exact, so any lip error is video-side.
- Verdict: USABLE with a fix. The lane works end to end and the character holds, but a bare
  portrait as first frame fights the prompt's scene. Phase 1 must feed Lane A a composed
  first frame (the storyboard panel: character IN the set), not just the character portrait —
  or use the ReferenceToVideo path with refs + a staged first frame. Do not ship portrait-first
  dialogue shots as-is; the mid-clip scene jump is not acceptable in a cut.

## Lane B — P0-B1 "James crosses to Kate" (blockout-guided video-to-video)

- Render command: `jobs\phase0-rigid-llm\comfy\p0-b1-build-graph.py submit`
  (graph built from `comfy-local\ref2va-audio-comparison-graph.json`: node 157 replaced with
  MiniMaxH3ReferenceToVideo, Kate+James refs; node 160 SenseNovaH3DistilledBridge; node 162
  VHS_LoadVideo full 124-frame Blender guide, format H3; node 163 MiniMaxH3AddGuide frame_idx 0)
- Take name: phase0-b1-james-crosses
- Output file:
- Prompt ID: e055d589-99bd-4b37-8cc3-8910c91144ed. Submitted 02:43:14 CST.
- Guide render time (Blender): 18 s for 124 frames + still (Workbench, 1280x704). Two script
  fixes needed first (Blender 5.2 layered-action API; parenting a child to a scaled object
  displaced James's head to the ceiling — fixed by keyframing head/face locations directly).
- H3 render time (submit to finished):
- Human minutes (hands-on, excluding render wait):
- Duration / resolution / fps (ffprobe):
- Motion survival: (did James walk left to right? did the camera dolly right track him?
  did Kate turn her head in the last 1.5 s? score each 0/1 and note what the model invented instead)
- Character consistency: (James orange suit + hat, Kate navy jacket vs portraits? two characters kept distinct?)
- Guide transfer: (does the output blocking match the Blender guide frame-for-frame, or only the first frame?)
- Verdict:

## Phase 1 lane-split recommendation

- (Write after both scores are in. Which lane is default, which shots earn Lane B, what Phase 1 builds first.)
