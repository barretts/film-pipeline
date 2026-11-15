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

Two attempts. B1 = full 124-frame guide (as designed). B1b = retry with the guide capped
at 22 frames (the repo's proven motion_ref overlap value).

### B1 (full guide) — STALLED, no output
- Render command: `jobs\phase0-rigid-llm\comfy\p0-b1-build-graph.py submit`
- Prompt ID: e055d589-99bd-4b37-8cc3-8910c91144ed. Submitted 02:43:14 CST.
- Blocker (exact): sampler stuck at 0/4 "Model Initializing" for 30 min. GPU idle at 38 W /
  38 C with 15.8 GB resident (not computing). `/interrupt` had no effect — the sampler was
  hung inside node execution. ComfyUI had to be killed by taskkill (PID 25208). Cause,
  from the log: the 124-frame guide batch is a 32,560-token prefix (VSA geometry line:
  prefix=(1889, 32560, 414, 880, 880, 414)); sampler init never got past it. No output file.
- Render time: 30+ min, no result. Human minutes: ~20 min (diagnosis, interrupt, taskkill, restart).

### B1b (22-frame guide cap) — RENDERED
- Render command: `jobs\phase0-rigid-llm\comfy\p0-b1b-build-graph.py submit`
  (identical graph except VHS_LoadVideo frame_load_cap 22, new take name/state file)
- Take name: phase0-b1b-james-crosses
- Output file: `comfy-local\output\phase0\b1b-james-crosses_00001.mp4` (1,790,345 bytes)
  (+ `b1b-james-crosses_00001-audio.mp4`, `b1b-james-crosses_00001.png`)
- Prompt ID: 308f034e-6421-4d25-ad1d-26f96f146bd2. Submitted 03:12:17 CST, success ~03:18:11 CST.
- Render time (submit to finished): 5 min 56 s (ComfyUI timestamps: execution_start
  1794733937833 → execution_success 1794734294296). Model init 58 s + 4 sampler steps
  x ~57 s/step + VAE decode. Fresh server after the B1 kill, so this includes model load.
- Human minutes (hands-on, excluding render wait): ~15 min (variant script, submit, polls).
  Lane B total hands-on across B1+B1b + Blender: ~60 min (Blender ~25 min incl. two API fixes
  and a re-render; graph builder ~15 min; submit/poll/stall diagnosis ~20 min).
- Duration / resolution / fps (ffprobe): 5.167 s, 1280x704, 24 fps, 124 frames, h264, video only.
- Motion survival, scored per element (1 = survived, 0 = did not):
  - James walks door-left to desk-right: 1. A real James in an orange-red survival suit
    enters through the door (t=1 s), crosses the room (t=2-3 s) and arrives at the desk (t=4 s).
  - Camera dollies right tracking him: 1. Framing moves right across the clip; the desk,
    windows and lamp enter frame as he crosses. The dolly is real, not a static shot.
  - Kate turns her head toward him in the last 1.5 s: 1. She looks down at her papers at
    t=3 s and looks up at him at t=4 s.
  - BUT: all three survived via the text prompt + the guide's first second, not via the
    full guide — the 22-frame cap only anchors the opening ~0.9 s; the rest is prompt-driven
    continuation. Do not read this as "the full guide transferred".
- Character consistency: GOOD. Same James throughout (orange suit, young man) and same Kate
  (face, silver-streaked hair, navy jacket, lanyard) — two characters kept distinct, no
  face-swapping. One miss: James wears his hood up, not the ear-flap hat from his portrait.
- Guide transfer: FAILED, literally. The guide's orange capsule was preserved as a literal
  floating orange egg in the centre of every frame (t=0 through t=4 s), while the model
  generated a separate real James walking beside it. AddGuide transfers the guide's
  pixels/layout faithfully — it does NOT interpret a blob as "a person walks here". The
  capsule's screen position even matches the guide (centre, camera-tracked). The shot is
  unusable as-is because of the artifact. The set transferred in spirit (grey room became
  a photoreal radio room with racks, windows, desk, lamp), but the flat grey floor/walls
  of the guide are still visible as flat grey.
- Verdict: LANE B WORKS MECHANICALLY, FAILS AS A GUIDE. The capped-guide render proves the
  ReferenceToVideo + AddGuide + bridge stack runs on this box in ~6 min. But a flat-colour
  blob blockout is the wrong guide format: the model copies the blobs as objects. Phase 1
  must change the guide, not the lane: render the blockout as depth / normals / edges
  (nothing solid-coloured to copy), or mask the characters out of the guide (room-only
  guide + prompt for the characters), or use the guide for the first frame + camera path
  only. Also: never submit a full-length guide — cap it (22 frames worked; the cap between
  22 and 124 that stalls init is unmeasured, find it in Phase 1 if a longer guide is wanted).

## Phase 1 lane-split recommendation

- Default lane is Lane A (keyframe image-to-video via the proven minimax_speech path):
  it renders, holds character, and syncs lips. Fix first: feed it a composed first frame
  (storyboard panel — character in the set), not a bare portrait, or the mid-clip scene
  jump recurs. Budget 10-15 min/shot cold, less warm.
- Lane B is NOT the default for blocking. It earns a shot only when the blocking/camera
  cannot be described in text — and only with a non-literal guide (depth/normal/edge or
  room-only) capped at ~22 frames, after Phase 1 measures the guide-length stall threshold.
  Do not build Phase 1 around full-length video guides; the H3 AddGuide path cannot take
  them on this box (32k-token prefix stalls sampler init, GPU idle).
- Phase 1 build order: (1) composed-first-frame Lane A (storyboard panel as first frame
  + character refs via ReferenceToVideo) and re-test the scene jump; (2) Lane B guide-format
  experiment (depth render vs room-only render, capped guide) on the same two-character
  shot; (3) only then the contracts/schemas automation. Do not automate either lane before
  its guide/first-frame format is proven — automation would just mass-produce the two
  failure modes found here (scene jump, blob leak).

## Timing log (all CST 2026-11-15, file-cabinet)

- 02:19 Piper kristin line 5.94 s; silence track 5.17 s
- 02:23 Blender guide rendered, 17.8 s (after two script fixes; final run 18.0 s)
- 02:28:58 Lane A submitted (prompt 11215c83); 02:42:16 success — 13 min 16 s
- 02:43:14 Lane B full-guide submitted (prompt e055d589); stalled 0/4, killed ~03:13 (30+ min, no output)
- 03:12:17 Lane B capped-guide submitted (prompt 308f034e); ~03:18:11 success — 5 min 56 s
- Commits on branch phase0-rigid-llm: 839a517 (draft), 43cde93 (audio + 141 frames),
  bfc7cb1 (Blender fixes), 0c005aa (Lane A scored, Lane B submitted), e5dcdab (B1 stall + B1b script)

## Lane B fix run — 2026-11-15, local only, no cloud (full record: results/lane-b-fixes.md)
Barrett's bar: motion/characters/framing all pass — the ONLY blocker was the orange guide artifact in front of Kate, and the 3D scene is a guide only, never to appear in the final output. B1b vs V5b frame comparison (guide | B1b | V5b at t=0,2,4s, results/compare-guide-b1b-v5b-f0*.png) verified Barrett right: B1b's door matches the guide (far left ~5% at t=2); V5b's door is displaced right ~20-25% of frame width and oversized, James ~1s behind, and V5b leaks MORE of the flat 3D room, not less.
- V1 prompt-mapping (TikTok <Video 1>/<Picture N> style, cap 22): 5m41s, motion 1/1, orange egg in every frame. Prompt cannot override AddGuide's latent anchor.
- V4 white silhouettes: 5m41s, white egg first ~2s, clean by f05. Colour was never the problem.
- V5b start/end anchors (1-frame first+last): 4m20s, REGRESSION — egg in every frame, whole clip pulled toward the flat guide, door displaced.
- V3 room-only guide: 5m10s, WINNER — no egg, door correct, motion 1/1, Kate head turn lands. Guide the camera + set only.
- V11 no guide at all: 4m04s, CO-WINNER, cleanest shot of the run — photoreal from frame 1, motion survives on prompt + refs alone. CORRECTION (2026-11-15, investigation + fix tests): NOT photoreal from frame 1 — Kate is a grey polygon frames 0-8, fully photoreal from frame ~24. The prompt still mentioned a blockout that was never fed in. See V11b below.
- V12 edge guide: 5m18s, FAIL — edge outline became a solid black silhouette man centre frame.
- V10 Lane A composed first frame (frame 97 of P0-A1 as first frame): 13m12s, PASS — one continuous shot, hard cut gone, lip sync 4/5.
- Not run: V2 depth (guide flat/unusable; two passing variants exist), V6 cap 5 (egg still in guide), V7 chunked (more anchoring = worse), V8 Wan 2.2 (installed, open follow-up — whole new lane, not a Lane B fix), V9 textured (solid shapes copy literally), LTX (not installed, do not download ~16GB without approval).
- Updated Lane B recommendation: default no-guide (V11) when blocking can be prompt-driven; room-only guide (V3) when the exact Blender camera path must be preserved. Never a guide containing character shapes. Lane A: composed first frame always.

## V11 grey-Kate fix tests + FINALS — 2026-11-15, local only (full record: results/lane-b-fixes.md)
- V11b prompt rewrite (all blockout language removed, same V11 setup, seed 5002, mode none): 4m56s (295.73 s). **WINNER — grey Kate GONE.** Kate fully photoreal from frame 0. Cause confirmed: the V1 prompt told the model a blockout existed that it never saw, and the model hallucinated a grey mannequin Kate. Motion 1/1, door left, James with correct ear-flap hat, Kate looks up by ~frame 72. Prompt ID c1bf3011-5755-4f1f-a502-58d61910d52e.
- V11c photoreal first-frame anchor (V11b prompt + AddGuide, V11 frame 24 anchored at frame 0, new `photo_first` mode): 4m14s (254.08 s). **Frame 0 also fixed** — Kate photoreal from frame 0 — but the camera overshoots: by frame 123 Kate is out of frame, shot ends close on James alone. Not a final. Prompt ID 7a43cd52-5d2d-4adb-8ea4-86df56408c1d.
- Updated Lane B default: **V11b — no guide, no blockout language in the prompt.** Never mention a blockout in a prompt unless a guide video is actually fed in.
- FINALS (comfy-local/output/phase0/, audio versions alongside, frame 0/1/5/10 checked):
  - `V11b-no-blockout_FINAL.mp4` — no trim, 124f, 5.167 s, the winner.
  - `V11-no-guide_FINAL.mp4` — trim at frame 24 (1.00 s), 100f, 4.167 s.
  - `V3-room-only_FINAL.mp4` — trim at frame 69 (2.875 s; frame 68 still flat, frame 69 first fully photoreal), 55f, 2.292 s.
  - `V10-composed_FINAL.mp4` — no trim, 141f, 5.875 s.
  - ffmpeg commands in results/lane-b-fixes.md and results/video-guide.md.
- Per-video lane + tech guide: results/video-guide.md — every video, lane first, tech second.
- ComfyUI stopped after the runs; GPU back to 825 MiB, 33°C, 6.78 W. Strata never touched.

## Story shots P0-B2 / P0-B3 — S1 "They listen together" and S2 "Kate turns to James" — 2026-11-15, local only (full record: results/video-guide.md)
The next two shots in sequence after B1, continuing the same story (B1 ends with James standing beside the desk). NOT the standalone S1-kate-tunes-dial / S2-kate-window-mug scenarios from the first brief — Barrett corrected that before anything was submitted; those prompts were never written or run. Both shots use the V11b winner workflow exactly: `lane-b-variant.py submit --mode none --bridge-alpha 0.15 --seed 5002`, prompt + Kate/James portraits only, no AddGuide, no guide video, no blockout language, 124f, 24 fps, 1280x704, silence audio `p0-b1-silence.wav` (so each render has an `-audio` version straight out of ComfyUI — no separate audio post-step). Prompts verbatim in `jobs/phase0-rigid-llm/prompts/S1-listen-together.txt` and `S2-kate-turns-to-james.txt`. No manual tweaking, no re-renders, no trims. Frame extracts (0, 1, 5, 10, 24, 72, 123) in `results/s1-s2-check/`; the 0/1/5/10 set also in `results/final-check/` under the FINAL names. Frame-extraction helper: `jobs/phase0-rigid-llm/extract-frames.ps1` (the inline `select='eq(n,..)'` filter does not survive the SSH → cmd → PowerShell quoting layers; a script file does).
- ComfyUI launch note: `Start-Process` from an SSH session dies when the session closes (PID 43768, empty log — same failure as the A1 run). This run launched it detached via WMI `Win32_Process.Create` with `cmd /c "... > comfy-s1-s2.log 2>&1"` (PID 45664); it survived the SSH disconnect and served both renders. That is the launch method to use from SSH. (Invoke-WebRequest to 127.0.0.1:8191 hangs from the SSH session — proxy handling; use curl.exe or the variant tool's own urllib calls instead.)
- GPU at start: 919 MiB, 30°C, 5.63 W, 4% — idle. Port 1234 listening turned out to be only the Tailscale Serve forwarder (tailscaled.exe); the Strata API returned nothing, no Strata/llama process exists, model not loaded. Strata was never running and never touched.

### S1 — P0-B2 "They listen together" — RENDERED, DUPLICATE KATE
- Render command: `jobs\phase0-rigid-llm\comfy\lane-b-variant.py submit --variant S1-listen-together --mode none --bridge-alpha 0.15 --seed 5002 --prompt-file jobs\phase0-rigid-llm\prompts\S1-listen-together.txt --take phase0\S1-listen-together`
- Take name: phase0/S1-listen-together
- Output file: `comfy-local\output\phase0\S1-listen-together_00001.mp4` (2,270,374 bytes)
  (+ `S1-listen-together_00001-audio.mp4`, `S1-listen-together_00001.png`)
- Prompt ID: 04a44b80-a4d4-438b-8e47-b78bbc2f2033. Submitted 12:50:13 CST, success 12:54:57 CST.
- Render time: 4m44s (284.39 s execution: 1794768613533 → 1794768897926).
- Duration / resolution / fps (ffprobe): 5.167 s, 1280x704, 24 fps, 124 frames, h264 (+ AAC audio in the -audio version).
- Motion survival, scored per element (1 = survived, 0 = did not):
  - Steady medium two-shot, then slow push-in toward the radio: 1. Framing tightens steadily
    f0 → f123; the wall clock and the lamp leave frame. A real push-in, not a static shot.
  - Kate turns the dial a fraction, then holds still: 1. Her hand moves to the dial by f10
    and is clearly turning it at f24/f72.
  - Kate nods once toward James in the last 1.5 s, without looking away from the radio: 0.5.
    At f123 she smiles slightly with her hand at the dial, but her head is still toward the
    radio — no clear nod toward James.
  - James does not move from the desk: 1. He stays beside the desk, leaning in, all clip.
- Character consistency: FAIL on count, GOOD otherwise. James is correct — orange-red suit,
  ear-flap hat (not hood up), same face throughout. But Kate is duplicated: a second
  silver-haired woman in a navy jacket with a lanyard sits at frame left in profile for
  frames 0–~100, so the clip has three figures in a two-character shot. The push-in nearly
  crops the duplicate out by f123 (only part of her face remains at the far left edge), but
  she is present through most of the clip. This duplication never happened in B1/V11b.
- Set: consistent WITHIN the clip — polar radio room, warm lamp right, snow windows, brass/green
  radio, pencil cup, same walls throughout. No grey polygon, no egg, no guide pixels, photoreal
  from frame 0.
- Verdict: NOT SHIPPABLE as-is. Motion, camera and frame 0 all pass, but an extra Kate breaks
  the shot and the "no additional characters" line. No re-render (verbatim-prompt run, no
  tweaking). The duplicate-Kate failure is the thing to watch for in the next two-shot.
- Final: `S1-listen-together_FINAL.mp4` (+ `-audio`) — stream copy, no trim. Listed as a final
  for completeness; the verdict above stands.

### S2 — P0-B3 "Kate turns to James" — RENDERED, USABLE WITH CAVEATS
- Render command: `jobs\phase0-rigid-llm\comfy\lane-b-variant.py submit --variant S2-kate-turns-to-james --mode none --bridge-alpha 0.15 --seed 5002 --prompt-file jobs\phase0-rigid-llm\prompts\S2-kate-turns-to-james.txt --take phase0\S2-kate-turns-to-james`
- Take name: phase0/S2-kate-turns-to-james
- Output file: `comfy-local\output\phase0\S2-kate-turns-to-james_00001.mp4` (2,359,200 bytes)
  (+ `S2-kate-turns-to-james_00001-audio.mp4`, `S2-kate-turns-to-james_00001.png`)
- Prompt ID: 40f05557-338d-4a3d-a6b5-f386b9307b5f. Submitted ~12:56:24 CST, success 13:00:39 CST.
- Render time: 4m15s (255.40 s execution: 1794768984530 → 1794769239934).
- Duration / resolution / fps (ffprobe): 5.167 s, 1280x704, 24 fps, 124 frames, h264 (+ AAC audio in the -audio version).
- Motion survival, scored per element (1 = survived, 0 = did not):
  - Camera dollies left slowly, circling slightly around the desk toward Kate: 1, mostly in
    the second half. Between f24 and f72 the viewpoint rotates around the desk (clock travels
    across the top of frame, lamp moves to the right edge, the window behind James comes into
    view). Frames 0–24 are nearly static.
  - Kate turns in her chair away from the radio to face James: 1. Clearly turned by f72,
    looking up at him, held through f123.
  - Kate gestures once toward the radio with her right hand: 0.5. Her hand is off the radio
    by f72, but no single clear gesture toward it is visible in the sampled frames.
  - Kate holds his gaze; James steps back half a step and nods in the last 1.5 s: 0.5. The
    mutual gaze clearly lands (f72–f123, her looking up at him, him looking down at her);
    James reads as a half-step back with a slight smile/head tilt at f123, but no crisp
    discrete nod is visible in the stills.
- Character consistency: GOOD on count, one miss on costume. Two characters only, no
  duplication; Kate correct throughout (navy jacket, cream sweater, lanyard with brass ring,
  silver-streaked hair). James: orange-red suit and face correct, but his hood is UP, not
  the ear-flap hat from his portrait — the same miss as V11/B1b. (S1 got the hat right;
  the hat is a coin flip across the no-guide runs: V11b and S1 correct, V11/B1b/V11c/S2 hood up.)
- Set: consistent WITHIN the clip — same room, lamp, radio console throughout; photoreal from
  frame 0, no grey polygon, no egg, no guide pixels. BUT the room does NOT match S1's room
  (or B1's): S2 is white fabric/tent walls and ceiling with a big rectangular window and a
  map on the wall; S1 is wood panelling with a sloped beamed ceiling. Cross-shot set
  continuity fails.
- Verdict: USABLE WITH CAVEATS. The turn-and-gaze beat is the strongest character moment of
  the no-guide runs, and this is the only S1/S2 shot with the correct character count. The
  hood and the set mismatch are the problems; neither is fixable by trimming.
- Final: `S2-kate-turns-to-james_FINAL.mp4` (+ `-audio`) — stream copy, no trim.

## Timing log, continued (all CST 2026-11-15, file-cabinet)

- 12:50:13 S1 submitted (prompt 04a44b80); 12:54:57 success — 4 min 44 s
- 12:56:24 S2 submitted (prompt 40f05557); 13:00:39 success — 4 min 15 s
