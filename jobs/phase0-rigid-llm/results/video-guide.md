# Video guide — what lane is each video, and what tech made it

Plain-language guide for Barrett. Every video from Phase 0 and the Lane B fix run, same shot unless noted: "James crosses to Kate" — James enters the polar station radio room through the door at frame left, walks to Kate at the radio desk at frame right, camera dollies right, Kate looks up at him. 124 frames, 24 fps, 5.17 s, 1280×704, unless noted.

Two further shots continue the story after B1 — P0-B2 "They listen together" and P0-B3 "Kate turns to James" — in their own section below. Same 124 frames, 24 fps, 5.17 s, 1280×704, same V11b no-guide workflow.

"Lane" means how the shot was driven. "Tech" means the model, the guide, and the prompt. What worked / what didn't is a secondary note under each one.

Lanes used here:
- **Lane A** — keyframe image-to-video. One still image (the first frame) + a prompt + voice. The model invents the motion from that still.
- **Lane B** — blockout-guided video-to-video. A Blender 3D blockout (rough grey shapes, camera move, timing) is fed in as a guide, plus reference portraits, and MiniMax re-renders it.
- **Lane B, room-only** — same as Lane B, but the guide contains only the room, camera and set. No characters in the guide at all.
- **Lane B, no-guide** — prompt + reference portraits only, no Blender guide at all. (Still filed under Lane B because it is the same two-character moving shot, not a Lane A talking-head.)

All Lane B videos below run locally on the 4060 Ti (16 GB) in ComfyUI, model MiniMax H3 ReferenceToVideo, SenseNova H3 distilled bridge alpha 0.15, 4-step turbo sampler, seed 5002, unless noted. No cloud was used for any of them.

---

## The two-character shot (James crosses to Kate)

### `b1b-james-crosses_00001.mp4` (+ `-audio` version)
- **Lane:** Lane B, full character guide, capped at 22 frames.
- **Tech:** Blender blockout (124f, orange capsule James, blue capsule Kate) fed via MiniMaxH3AddGuide, cap 22 frames, original B1 prompt ("follow the supplied guide video"), bridge alpha 0.15. Render 5m56s.
- **What worked:** walk, dolly, Kate's head turn — all landed. Door location correct.
- **What didn't:** the orange capsule was copied literally as a floating orange egg in the centre of every frame, in front of Kate. Unusable as a final.

### `V1-prompt-map_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, full character guide, capped at 22 frames.
- **Tech:** Same guide and cap as B1b. Prompt rewritten in the TikTok style: "<Video 1> is an untextured basic-shape 3D blockout… match them to the blockout figures by position and action. The blockout figures are uncolored, so do not use color to identify them." Render 5m41s.
- **What worked:** motion and characters, same as B1b.
- **What didn't:** orange egg in every frame, same as B1b. The prompt alone cannot override AddGuide — the guide is anchored in the latent, not a text hint.

### `V3-room-only_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, room-only guide.
- **Tech:** Blender blockout with the characters hidden — camera + set only (room, door, desk, lamp). V1 prompt-map, AddGuide cap 22, bridge alpha 0.15. Render 5m10s.
- **What worked:** walk, dolly, head turn, door correct. No orange egg, no capsule, no character shape to copy.
- **What didn't:** the first ~3 seconds are the flat grey guide room morphing into photoreal — frame 0 is literally the raw grey room, frame 24 James is photoreal but the room is still flat, frame 48 partly photoreal, fully photoreal around frame 72–80. See `V3-room-only_FINAL.mp4` for the trimmed final.
- **Verdict:** winner for control — use when the exact Blender camera path / door location must be preserved.

### `V4-silhouette_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, white-silhouette guide.
- **Tech:** Blender blockout re-rendered as white silhouettes on black. V1 prompt, AddGuide cap 22, bridge alpha 0.15. Render 5m41s.
- **What worked:** motion and characters.
- **What didn't:** the white silhouette was copied as a white egg in front of the window for the first ~2 s, clean by frame ~120. Colour was never the problem — AddGuide copies any character shape literally.

### `V5b-start-end_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, start/end anchors only.
- **Tech:** AddGuide with 1-frame anchors only — first guide frame at frame 0, last guide frame at frame 123 (LoadImage on guide PNGs; VHS_LoadVideo cap 1 returns an empty batch). V1 prompt, bridge alpha 0.15. Render 4m20s.
- **What worked:** looks good overall at a glance.
- **What didn't:** orange egg in every frame, larger than B1b, and the door is displaced right ~20–25% of frame width vs the guide/B1b, James ~1 s behind. The whole flat 3D room persists in all frames. Start/end anchors trade spatial accuracy for nothing. Do not use.

### `V11-no-guide_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, no-guide.
- **Tech:** No AddGuide, no guide video at all. Prompt + Kate and James reference portraits only (MiniMaxH3ReferenceToVideo + SenseNova bridge alpha 0.15). V1 prompt-map — note: it still says "<Video 1> is an untextured basic-shape 3D blockout" even though no Video 1 was fed in. Render 4m04s, fastest of the run.
- **What worked:** walk, dolly, head turn, door left, James enters and crosses, Kate looks up. No orange egg, zero guide pixels by construction.
- **What didn't:** Kate is a flat grey/white faceted polygon for frames 0–8, resolving frame 9–10, fully photoreal from frame ~24. The room and James are photoreal from frame 0. See `V11-no-guide_FINAL.mp4` for the trimmed final, and V11b/V11c below for the re-tests.

### `V12-edge_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, edge-map guide.
- **Tech:** Blender blockout re-rendered as an edge/outline map. V1 prompt, AddGuide cap 22, bridge alpha 0.15. Render 5m18s.
- **What worked:** motion and characters.
- **What didn't:** the edge outline was copied as a solid black silhouette of a walking man, centre frame, in every shot. An edge map is still a literal guide in a different colour. Do not use.

### `V11b-no-blockout_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, no-guide.
- **Tech:** Same as V11 (no AddGuide, bridge alpha 0.15, seed 5002, prompt + Kate and James portraits only), but the prompt was rewritten with ALL blockout language removed — no "<Video 1>", no "blockout", no "untextured basic-shape", no "blockout figures". Plain blocking: James enters left, crosses to Kate at the desk right, camera dollies right, she looks up. Render 4m56s (295.73 s execution).
- **Question it answers:** does the grey-polygon Kate in V11 frames 0–8 come from the prompt telling the model a blockout exists that it never saw? **Yes — confirmed.** Kate is fully photoreal from frame 0. No grey polygon at any frame. The grey Kate was the model hallucinating the blockout it was told about, not a cold-start. Cause (1) from the investigation is ruled out as the main cause.
- **What worked:** walk, dolly, head turn — all landed, and better than V11: James wears the correct ear-flap hat (not hood up), Kate is writing at the desk then looks up at him by frame ~72, door at frame left, both in frame at frame 123.
- **What didn't:** nothing in the frame 0–10 check. This is the winner.
- **Final:** `V11b-no-blockout_FINAL.mp4` (no trim, 124f, 5.17 s) + `-audio` version.

### `V11c-photo-first_00001.mp4` (+ `-audio`)
- **Lane:** Lane B, photoreal first-frame anchor.
- **Tech:** Same as V11b (no-blockout prompt, seed 5002, bridge alpha 0.15), plus one AddGuide: a single photoreal PNG — V11 frame 24, Kate fully photoreal at the desk, James inside the door — anchored at frame 0 (`photo_first` mode in `lane-b-variant.py`). This is the V10 recipe, adapted to Lane B. Render 4m14s (254.08 s execution).
- **Question it answers:** does a photoreal first-frame anchor make Kate photoreal from frame 0? **Yes — also works.** Kate is fully photoreal from frame 0, no grey polygon.
- **What worked:** frame 0 is photoreal, James enters left, Kate at desk right, head turn happens (frame ~96, Kate looking up at James).
- **What didn't:** the blocking drifts. The anchor was V11 frame 24, which already had the camera right of the start position, and the model kept dolling right from there — by frame 123 the camera is close on James in profile and Kate is out of frame entirely. James also wears his hood up, not the ear-flap hat. So V11c passes the frame-0 test but loses the two-shot ending. Not promoted to a FINAL — V11b is the better shot.
- **Caveat, as noted before the render:** frame 24 shows James already inside, so this test starts the blocking mid-walk. It tested the mechanism (photoreal anchor → photoreal frame 0), not the final blocking. A production version would use a photoreal first frame matching the shot's start.

---

## The next two story shots (P0-B2, P0-B3) — continuing from B1

Same film, "Signal in the Snow", scene S01. B1 ends with James standing beside the desk; these two are the next shots in sequence. Both use the V11b winner workflow exactly — Lane B, no-guide, prompt + Kate and James reference portraits only, MiniMax H3 ReferenceToVideo, SenseNova bridge alpha 0.15, 4-step turbo sampler, seed 5002, mode `none`, no AddGuide, no guide video, no blockout language in the prompt. Silence audio (`p0-b1-silence.wav`) via the H3 audio VAE, so each render has an `-audio` version alongside. No manual tweaking, no re-renders. Prompts are verbatim in `jobs/phase0-rigid-llm/prompts/S1-listen-together.txt` and `S2-kate-turns-to-james.txt`. Frame extracts (0, 1, 5, 10, 24, 72, 123) in `results/s1-s2-check/`; the 0/1/5/10 set is also in `results/final-check/` under the FINAL names.

### `S1-listen-together_00001.mp4` (+ `-audio`) — P0-B2, "They listen together"
- **Lane:** Lane B, no-guide.
- **Tech:** V11b workflow as-is. Prompt: Kate seated at the desk right, right hand on the dial; James beside the desk centre, leaning in to listen; steady medium two-shot, then a slow push-in toward the radio; Kate turns the dial a fraction, holds still, nods once toward James in the last 1.5 s without looking away from the radio; James does not move from the desk. Render 4m44s (284.39 s execution). Prompt ID 04a44b80-a4d4-438b-8e47-b78bbc2f2033.
- **What worked:** photoreal from frame 0 — no grey polygon, no egg, no guide pixels. The push-in is real (framing tightens steadily f0 → f123; the wall clock and lamp leave frame). Kate's dial turn lands (hand moves to the dial by f10, clearly turning it at f24/f72). James stays at the desk, leaning in, and wears the correct ear-flap hat (not hood up). The room is a consistent polar radio room throughout: warm lamp right, snow windows, brass/green radio, pencil cup.
- **What didn't:** **Kate is duplicated.** A second silver-haired woman in a navy jacket with a lanyard sits at frame left in profile for frames 0–~100 — three figures in a two-character shot. The push-in nearly crops her out by f123 (only part of her face remains at the far left edge), but she is present through most of the clip. The final nod is also only partial: at f123 Kate smiles slightly with her hand at the dial, but her head is still toward the radio — no clear nod toward James.
- **Verdict:** not shippable as-is. The motion, camera and photoreal frame 0 all pass, but an extra Kate breaks the shot and the "no additional characters" line. No re-render was done (verbatim-prompt run, no tweaking). The duplicate-Kate failure is new — B1/V11b never duplicated a character — and it is the thing to watch for in the next two-shot.

### `S2-kate-turns-to-james_00001.mp4` (+ `-audio`) — P0-B3, "Kate turns to James"
- **Lane:** Lane B, no-guide.
- **Tech:** V11b workflow as-is. Prompt: Kate seated at the desk right; James beside the desk centre, facing Kate; camera dollies left slowly, circling slightly around the desk toward Kate; Kate turns in her chair away from the radio to face James, gestures once toward the radio with her right hand, holds his gaze; James steps back half a step and nods in the last 1.5 s. Render 4m15s (255.40 s execution). Prompt ID 40f05557-338d-4a3d-a6b5-f386b9307b5f.
- **What worked:** photoreal from frame 0 — no grey polygon, no egg, no guide pixels. Two characters only, no duplication. The beat of the shot lands: Kate turns in her chair to face James (clearly by f72, held through f123), looking up at him, and they hold each other's gaze to the end; James reads as a half-step back with a slight smile/head tilt at f123. The dolly left / circling is real, mostly in the second half — between f24 and f72 the viewpoint rotates around the desk (clock travels across the top of frame, lamp moves to the right edge, the window behind James comes into view). Within-shot consistency is good: same room, same lamp, same radio console throughout.
- **What didn't:** James wears his hood up, not the ear-flap hat from his portrait — the same miss as V11/B1b (S1 got the hat right, S2 didn't). The gesture toward the radio and the discrete nod are only partial in the sampled frames: her hand is off the radio by f72 but no single clear gesture toward it is visible, and the nod reads as a head tilt/smile rather than a crisp nod. **The set does not match S1's room** (or B1's): S2's room is white fabric/tent walls and ceiling with a big rectangular window and a map on the wall; S1's is wood panelling with a sloped beamed ceiling. Same film, different rooms — cross-shot set continuity fails.
- **Verdict:** usable with caveats. The two-shot beat (Kate turns, they hold the gaze) is the strongest character moment of the no-guide runs, and it is the only S1/S2 shot with the correct character count. The hood and the set mismatch are the problems; neither is fixable by trimming.

---

## The dialogue shot (Kate at the radio) — Lane A

### `phase0-a1-kate-radio_00001_.mp4` (in `comfy-local/output/minimax-speech/`)
- **Lane:** Lane A, keyframe image-to-video.
- **Tech:** `tools/minimax_speech.py submit`, first frame = bare Kate portrait, 141 frames @ 24 fps, 704×1280, seed 2801, Piper "kristin" voice line (5.94 s audio, so 141 frames not 124). Render 13m16s.
- **What worked:** character consistency excellent, lip sync 4/5 (audio envelope correlation 0.992, 0 ms lag).
- **What didn't:** the bare portrait first frame fought the prompt's scene — the clip is two shots, tight portrait against a plain wall for ~2.8 s, then a hard cut at ~3 s to the desk scene.

### `phase0-a1-v10-composed_00001_.mp4` (in `comfy-local/output/minimax-speech/`)
- **Lane:** Lane A, keyframe image-to-video, composed first frame.
- **Tech:** Same as P0-A1 (same prompt, audio, seed 2801, 141f, 704×1280), but the first frame is frame 97 of the P0-A1 output — Kate at the desk with hands on the dial, snow window, lamp, radio — a storyboard panel with the character IN the set, not a bare portrait. Render 13m12s.
- **What worked:** one continuous shot, no hard cut, lip sync 4/5. Frame 0 is fully photoreal — no morph, no trim needed.
- **Verdict:** Lane A recipe — first frame is always the composed panel, never a bare portrait. This file is already a final as-is; see `V10-composed_FINAL.mp4`.

---

## Finals (trimmed, everything fully rendered)

Made with ffmpeg trim + re-encode (libx264, same 24 fps). Audio versions trimmed by the same amount so audio stays in sync. Each final was checked frame by frame at 0, 1, 5 and 10 — no grey polygon, no flat grey room, no orange egg, no guide pixels in the final cut.

- `V11b-no-blockout_FINAL.mp4` (+ `-audio`) — **the winner, no trim.** 124 frames, 5.167 s, 1280×704. Kate photoreal from frame 0, James enters left with ear-flap hat, crosses, Kate looks up, both in frame at the end. Stream copy of the V11b render.
- `V11-no-guide_FINAL.mp4` (+ `-audio`) — trimmed to start at frame 24 (1.00 s), the first fully photoreal frame of the original V11. 100 frames, 4.167 s. James entering left, Kate photoreal at desk. Audio trimmed 1.0 s.
- `V3-room-only_FINAL.mp4` (+ `-audio`) — trimmed to start at frame 69 (2.875 s), the first fully photoreal frame of V3 (verified frame by frame: frame 68 still flat grey walls / white ceiling, frame 69 walls gain panel seams, ceiling goes dark, lamp appears). 55 frames, 2.292 s. James mid-walk at left, Kate at desk right, head turn still in the cut (~1.1 s in). Audio trimmed 2.875 s.
- `V10-composed_FINAL.mp4` — **no trim needed; V10 is photoreal from frame 0.** Stream copy of `minimax-speech/phase0-a1-v10-composed_00001_.mp4`, 141 frames, 5.875 s, 704×1280, audio already in the file.
- `S1-listen-together_FINAL.mp4` (+ `-audio`) — **no trim; S1 is photoreal from frame 0.** Stream copy of the S1 render, 124 frames, 5.167 s, 1280×704. Listed as a final for completeness, but **not shippable as-is** — Kate is duplicated for most of the clip (see the P0-B2 entry above).
- `S2-kate-turns-to-james_FINAL.mp4` (+ `-audio`) — **no trim; S2 is photoreal from frame 0.** Stream copy of the S2 render, 124 frames, 5.167 s, 1280×704. Usable with caveats — the turn-and-gaze beat lands, but James's hood is up (not the ear-flap hat) and the set does not match S1's room (see the P0-B3 entry above).

ffmpeg commands used (on file-cabinet, from `F:\film-pipeline`):
```
ffmpeg -i comfy-local\output\phase0\V11-no-guide_00001.mp4 -vf trim=start_frame=24,setpts=PTS-STARTPTS -c:v libx264 -pix_fmt yuv420p -crf 18 comfy-local\output\phase0\V11-no-guide_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\V11-no-guide_00001-audio.mp4 -vf trim=start_frame=24,setpts=PTS-STARTPTS -af atrim=start=1.0,asetpts=PTS-STARTPTS -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac comfy-local\output\phase0\V11-no-guide_FINAL-audio.mp4
ffmpeg -i comfy-local\output\phase0\V11b-no-blockout_00001.mp4 -c copy comfy-local\output\phase0\V11b-no-blockout_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\V11b-no-blockout_00001-audio.mp4 -c copy comfy-local\output\phase0\V11b-no-blockout_FINAL-audio.mp4
ffmpeg -i comfy-local\output\phase0\V3-room-only_00001.mp4 -vf trim=start_frame=69,setpts=PTS-STARTPTS -c:v libx264 -pix_fmt yuv420p -crf 18 comfy-local\output\phase0\V3-room-only_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\V3-room-only_00001-audio.mp4 -vf trim=start_frame=69,setpts=PTS-STARTPTS -af atrim=start=2.875,asetpts=PTS-STARTPTS -c:v libx264 -pix_fmt yuv420p -crf 18 -c:a aac comfy-local\output\phase0\V3-room-only_FINAL-audio.mp4
ffmpeg -i comfy-local\output\minimax-speech\phase0-a1-v10-composed_00001_.mp4 -c copy comfy-local\output\phase0\V10-composed_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\S1-listen-together_00001.mp4 -c copy comfy-local\output\phase0\S1-listen-together_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\S1-listen-together_00001-audio.mp4 -c copy comfy-local\output\phase0\S1-listen-together_FINAL-audio.mp4
ffmpeg -i comfy-local\output\phase0\S2-kate-turns-to-james_00001.mp4 -c copy comfy-local\output\phase0\S2-kate-turns-to-james_FINAL.mp4
ffmpeg -i comfy-local\output\phase0\S2-kate-turns-to-james_00001-audio.mp4 -c copy comfy-local\output\phase0\S2-kate-turns-to-james_FINAL-audio.mp4
```

## How to read this guide — lane, in one line

| Video | Lane | Tech, one line |
|---|---|---|
| `b1b-james-crosses_00001` | Lane B, full character guide, cap 22 | Blender capsules + AddGuide, original prompt, 5m56s |
| `V1-prompt-map_00001` | Lane B, full character guide, cap 22 | Same guide, TikTok-style prompt-map, 5m41s |
| `V3-room-only_00001` | Lane B, room-only guide | Camera + set only, no characters, V1 prompt, 5m10s |
| `V4-silhouette_00001` | Lane B, white-silhouette guide | White shapes on black, V1 prompt, 5m41s |
| `V5b-start-end_00001` | Lane B, start/end anchors only | 1-frame guides at 0 and 123, V1 prompt, 4m20s |
| `V11-no-guide_00001` | Lane B, no-guide | Prompt + portraits only, V1 prompt (still mentions a blockout), 4m04s |
| `V12-edge_00001` | Lane B, edge-map guide | Edge outline guide, V1 prompt, 5m18s |
| `V11b-no-blockout_00001` | Lane B, no-guide | Prompt + portraits only, blockout language removed, 4m56s |
| `V11c-photo-first_00001` | Lane B, photoreal first-frame anchor | V11b prompt + AddGuide, V11 frame 24 at frame 0, 4m14s |
| `phase0-a1-kate-radio_00001_` | Lane A, keyframe image-to-video | Bare portrait first frame, Piper voice, seed 2801, 13m16s |
| `phase0-a1-v10-composed_00001_` | Lane A, keyframe image-to-video | Composed first frame (Kate at desk), same audio/seed, 13m12s |
| `S1-listen-together_00001` | Lane B, no-guide | P0-B2 "They listen together", push-in, Kate dial turn, 4m44s — Kate duplicated, not shippable |
| `S2-kate-turns-to-james_00001` | Lane B, no-guide | P0-B3 "Kate turns to James", dolly left, turn-and-gaze beat lands, 4m15s — James hood up, set ≠ S1 |

## Not run, and why

- **V2 depth guide** — guide as rendered was flat/unusable (range 50–59, stdev 1.8). Not re-rendered: V3 and V11 already pass, and V4/V12 prove any character-shaped guide is copied literally.
- **V6 cap 5 + alpha 0.05, V7 chunked** — more anchoring = more literal copy (V5b proved it). Cannot pass Barrett's bar.
- **V8 Wan 2.2 TI2V-5B** — model IS installed, but it is a whole new lane, not a Lane B fix. Open follow-up.
- **V9 textured / white-clay guide** — solid shapes copy literally whatever the colour (V4 proved it); the textured render came out overexposed white clay anyway.
- **LTX-2.3 FP8** — not installed anywhere on the box. Not downloaded (~16 GB) without approval.
- **Cloud H3 Max reference-to-video** — the TikTok workflow is a Comfy Cloud Partner Node, 1 credit per run, login-gated. Not used. Local only, per Barrett.
