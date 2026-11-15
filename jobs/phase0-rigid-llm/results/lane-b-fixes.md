# Lane B fix run — local only, no cloud. Measured on file-cabinet, 2026-11-15. Do not invent numbers.

## Barrett's rule (2026-11-15, restated on V5b)
The 3D scene is only ever a guide. It should not be in the final output anywhere. Motion, characters, framing pass; the artifact must be gone entirely.

## Barrett's bar (2026-11-15, after watching B1b / V1 / V4)
Motion, characters, framing all pass — "all 3 were good". The ONLY blocker is the thing that stays in frame: the orange guide artifact goes in front of Kate and should not be there at all. Pass/fail for this fix run is therefore: **is the orange/white guide artifact gone ENTIRELY?** Not improved, not shorter — gone. Score the artifact explicitly per variant.

Source: TikTok workflow `comfy/API_Minimax_Max_TrainScene.json` (H3 Max cloud reference-to-video, 768P, duration 15, 5 images, switches off, LoadVideo UNPLUGGED — video_1 null). Used as prompt/format reference only. Local runs use MiniMax H3 ReferenceToVideo + SenseNova bridge + MiniMaxH3AddGuide via `comfy/lane-b-variant.py`.

Baseline (Phase 0, for comparison):
- B1b: 22-frame original guide, original prompt, bridge alpha 0.15, 5m56s. Walk/dolly/head-turn 1/1, but orange capsule copied literally as a floating orange egg every frame. Unusable.

## Variants

### V1 — prompt-mapping (TikTok <Video 1>/<Picture N> language), original guide, cap 22, alpha 0.15 — RENDERED, EGG STILL PRESENT
- Prompt: `prompts/V1-prompt-map.txt`
- Prompt ID: f3de7d7b-eca2-4f77-89c6-2af7c0b74050. Execution 03:54:43-04:00:24 CST, 5m41s.
- Output: `comfy-local/output/phase0/V1-prompt-map_00001.mp4` (1,989,852 bytes, 5.167s, 1280x704, 24fps, 124f)
- Motion: walk 1/1, dolly 1/1, Kate head turn 1/1 (f05: James at desk, Kate looking up at him).
- Character: GOOD — same James (orange suit, hood up not ear-flap hat, as in B1b) and Kate (navy jacket, lanyard, silver-streaked hair).
- Guide literalness: FAILED. Orange egg present in EVERY frame, same as B1b. f01 is literally the raw guide frame; f03/f05 show a real James and Kate PLUS the floating orange egg centre frame (beige head ball visible above Kate's head at f05).
- Verdict: prompt-mapping alone does NOT fix AddGuide literalness. Locally the guide is anchored in latent, not a text hint the prompt can override — unlike the cloud reference-to-video path in the TikTok workflow. The fix must be in the guide format, not the prompt.

### V2 — depth guide
- Guide: `guide/depth.mp4` — Blender 5.2 EEVEE Z pass, Normalize compositor. CHECKED frame 60: range 50-59, stdev 1.8, near-flat dark grey. UNUSABLE as rendered (background infinity compresses range). MapRange node does not exist in Blender 5.2 compositor; re-render with Math-node clamp (11-depth)/6 planned.
- Status: NOT RUN — guide failed verification.

### V3 — room-only guide, V1 prompt, cap 22, alpha 0.15 — RENDERED, ARTIFACT GONE, WINNER
- Guide: `guide/room-only.mp4` — Workbench, characters hidden. Frame 60 verified: room, door, desk, lamp only (small ball at desk is the lamp).
- Prompt ID: 6edc70b2-1d94-4474-b9f8-c8d2dc1ce3c1. Execution 1794738516986-1794738827404, 5m10s.
- Output: `comfy-local/output/phase0/V3-room-only_00001.mp4` (5.167s, 1280x704, 124f)
- Motion: walk 1/1, dolly 1/1, Kate head turn 1/1 (f05: James at the desk, Kate looking up at him).
- Character: GOOD — same James (orange suit, hood up) and Kate (navy jacket, lanyard, silver-streaked hair).
- Door: CORRECT — door at ~28% at t=0, far left at t=2, matching the guide and B1b. Keeps B1b's blocking accuracy.
- Artifact: PASS by Barrett's bar — NO orange egg, no white egg, no capsule, no flat guide pixels in the final frames. f01 is the raw room-only guide frame (flat empty room, tan door) for the first ~0.9s, same as B1b/V1 f01, but there is no character shape to copy; by f03 the room is fully photoreal.
- Verdict: WINNER. Room-only guide keeps B1b's door/blocking and removes the artifact entirely. This is the Lane B recipe: guide the camera + set only, characters from reference images + prompt.

### V11 — no guide at all (mode none), V1 prompt, alpha 0.15 — RENDERED, CLEANEST SHOT OF THE RUN
- Prompt ID: 91bdcc83-59dd-4d85-a4e4-27349c0ef29a. Execution 1794738874253-1794739118176, 4m04s (fastest yet — no guide VSA prefix).
- Output: `comfy-local/output/phase0/V11-no-guide_00001.mp4` (5.167s, 1280x704, 124f)
- Motion: walk 1/1, dolly 1/1, Kate head turn 1/1 (f05: James at the desk, Kate looking up at him).
- Character: EXCELLENT — same James (orange suit, hood up) and Kate (navy jacket, lanyard, silver-streaked hair).
- Door: frame left at t=0, James entering through it with snow outside; blocking (enter left, cross to Kate at desk right) matches the blockout, though the camera path is prompt-invented, not the exact Blender path.
- Artifact: PASS — zero guide pixels by construction (no AddGuide at all), and no flat-room flash at f01 either, unlike V3 which starts on the raw guide frame. Photoreal from frame 1.
- Verdict: CO-WINNER, cleanest of the run. For a simple cross-room walk, prompt + reference images are enough — the Blender guide was not needed for this shot. V3 remains the controlled answer when the exact Blender camera path must be preserved; V11 is the answer when the blocking can be prompt-driven. Lane B's guide is a fallback for shots where the camera path must be exact, not a default.

### V4 — white silhouettes on black, V1 prompt, cap 22, alpha 0.15 — RENDERED, WHITE EGG STILL PRESENT (first ~2s only)
- Prompt ID: 6d7bc7f5-e66f-42c2-8acb-0b4b14c08e41 (retry; first attempt a4e405e4 failed in the sampler with OSError Errno 22, tqdm stdout flush in ComfyUI's logger — infra, not the guide; fixed by restarting ComfyUI with stdout redirected to `comfy/comfy-laneb.log`). Execution 1794737356018-1794737696700, 5m41s.
- Output: `comfy-local/output/phase0/V4-silhouette_00001.mp4` (5.167s, 1280x704, 124f)
- Motion: walk 1/1, dolly 1/1, Kate head turn 1/1.
- Character: GOOD — same James (orange suit, hood up) and Kate (navy jacket, lanyard).
- Guide literalness: FAILED, but differently. f01 is literally the raw silhouette frame; f03 shows a real James and Kate PLUS a white egg centre frame in front of the window; f05 is CLEAN — no egg, James at the desk, Kate looking up at him. The literal copy only lasts as long as the anchored clip (~0.9s for 22 frames, visibly fading by t=3s); after that prompt continuation takes over.
- Verdict: colour was never the problem — AddGuide copies ANY guide shape literally for the anchored duration. Shorter anchor = shorter artifact. This is the case for V5 (start/end, 1-frame anchors) and V6 (cap 5).

### V5 — start/end AddGuide only — FAILED, REGRESSION
- First attempt (V5): VHS_LoadVideo cap 1 returns an empty batch — ImageResizeKJv2 RuntimeError "stack expects a non-empty TensorList". Fixed in lane-b-variant.py: start/end now uses LoadImage on guide/frames/frame_0001.png and frame_0124.png.
- Retry (V5b): Prompt ID 64b680c3-576b-40bc-83a7-c7332835ad69. Execution 1794738157934-1794738417654, 4m20s (faster — 1-frame anchors).
- Output: `comfy-local/output/phase0/V5b-start-end_00001.mp4` (5.167s, 1280x704, 124f)
- Motion: walk 1/1, dolly 1/1 — but in a FLAT guide world, not the photoreal room. The end-frame anchor at 123 appears to pull the whole clip toward the guide's flat grey look.
- Character: James good; Kate present at the desk (f05, looking at James) but small / partly obscured by the egg.
- Artifact: FAIL by Barrett's bar — orange egg front-and-centre in EVERY frame, larger and more dominant than V1/V4, directly in front of Kate at f05. Worse than the 22-frame cap.
- Verdict: start/end anchors are worse, not better. Do not use.
- Barrett's take (2026-11-15, on V5b-start-end_00001-audio): "It just showed up. It looks good, but the other Lane B was better because it got the door location right." So V5b is good overall, but B1b (22-frame capped guide) wins on door location / spatial accuracy. Target for the remaining variants: keep B1b's door/blocking accuracy while removing ALL guide pixels from the final — not just the orange egg, any 3D-scene pixels.

### V6 — strength / denoise tweak
- Plan: cap 5 (minimum valid AddGuide clip) + bridge alpha 0.05, original guide, V1 prompt.
- Status: TBD

### V7 — chunked guide
- Mode: chunked — 22f guide at frame 0 + 22f guide (frames 103-124) at frame 102, chained AddGuide nodes.
- Status: TBD

### V8 — Wan 2.2 TI2V-5B
- Model FOUND: `E:\SwarmUI\Models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors` + `wan2.2_vae.safetensors`, text encoders qwen_3_4b / umt5_xxl_fp8 present. LTX: NO model file found anywhere — LTX variant NOT RUN, recorded as missing (do not download without Barrett approval; ~16GB FP8).
- Status: TBD

### V9 — textured (EEVEE lit) guide
- Guide: `guide/textured.mp4` — EEVEE, Principled materials, Sun + Area light. Frame 60 verified: OVEREXPOSED white clay, colors washed out (Sun 3.0 + Area 250 too strong). Recorded as white-clay guide, not a true textured test.
- Status: TBD

### V10 — Lane A composed first frame
- Plan: same Kate shot, first frame = a composed Kate-in-set frame (from P0-A1 desk phase), not bare portrait. Test whether the ~3s hard cut disappears.
- Status: TBD

## B1b vs V5b — frame comparison, verified empirically (2026-11-15)
Frames extracted at fps=1 (t=0,2,4s) from guide, B1b, V5b, composited guide | B1b | V5b.
Comparison images: `results/compare-guide-b1b-v5b-f01.png`, `...-f03.png`, `...-f05.png`.

- t=0: Guide door is at ~28% frame width, behind the egg; James at the door. B1b reproduces it faithfully (egg at ~28%, door frame behind it, no real James yet). V5b shows a real James entering through an OPEN door at frame left (~5-15%) — a plausible door, but NOT the guide door: it is in the side wall, and V5b's egg is at ~60% (vs guide ~30%), with windows invented on the right that are not in the guide at t=0. V5b's framing is already shifted right at t=0.
- t=2: Guide door at far left (~5-10%), egg centre (~30%), Kate blue egg at desk right (~75%). B1b matches: real James at ~5-15% walking past the door frame at ~5%, egg at ~35%. V5b: door at ~25-35% (tan, large), egg at ~60%, James at ~25%. V5b's door is displaced right by ~20-25% of frame width (~250-320px at 1280) vs guide/B1b, and oversized.
- t=4: Guide egg ~30%, Kate blue egg at desk ~65%. B1b matches: James arrived at the desk (~10%), Kate centre (~55%) looking up at him, egg ~35%. V5b: James still mid-stride at ~30% (has not arrived, ~1s behind), egg ~60%, Kate at desk right (~80%). Whole V5b framing shifted right ~30% vs guide.
- Guide leakage: V5b is WORSE, not cleaner. The entire flat 3D room persists in all V5b frames — flat grey walls/floor, tan door panel, cartoon windows with blue sky/snow, wooden desk. B1b's room becomes photoreal by t=4 (radio racks, windows, lamp, desk). The end-frame anchor at 123 appears to pull the whole clip toward the flat guide.
- Verdict: Barrett is CORRECT — B1b wins on door location (by ~20-25% frame width at t=2) and on walk timing (James arrives by t=4 in B1b, still mid-stride in V5b). Start/end anchors trade spatial accuracy for nothing: they do not remove the artifact, they shift the framing and increase guide leakage. Do not use start/end.
- Implication: the winning variant must keep B1b's 22-frame capped guide (the thing that preserves door/blocking) while removing ALL guide pixels from the final. Candidates, in order: room-only guide (no characters to copy, V3 running), edge guide (outlines only, no solid pixels), no-guide (prompt + refs only, V11), depth (grayscale, no solid colour).

## Guide-format notes (Blender 5.2.2)
- Engine enum is `BLENDER_EEVEE`, not `BLENDER_EEVEE_NEXT`.
- Compositor node tree is `scene.compositing_node_group` (new node group), not `scene.node_tree`; Composite node is `NodeGroupOutput`.
- `CompositorNodeMapRange` does not exist in 5.2. Use Math nodes: (11 - depth) / 6, clamped.
- `scene.eevee.use_soft_shadows` does not exist; use `scene.eevee.use_shadows`.
- Workbench variants render ~18s; EEVEE variants ~63-68s for 124 frames.

### V12 — edge guide, V1 prompt, cap 22, alpha 0.15 — RENDERED, NEW ARTIFACT: BLACK SILHOUETTE
- Prompt ID: 0f16c4a1-3351-4bd9-86bc-5318fe6acb21. Execution 1794739239421-1794739557805, 5m18s.
- Output: `comfy-local/output/phase0/V12-edge_00001.mp4` (5.167s, 1280x704, 124f)
- Motion: walk 1/1, dolly 1/1, Kate head turn 1/1 (f05: James at the desk, Kate looking up at him).
- Character: GOOD — same James (orange suit, hood up) and Kate (navy jacket, lanyard).
- Artifact: FAIL by Barrett's bar — no orange egg, but the edge-map James outline was copied as a SOLID BLACK SILHOUETTE of a walking man, centre frame in every shot (f03 in front of the window, f05 standing behind Kate in front of the radio racks). The model treats an edge outline as a dark figure. f01 is literally the edge map (white with thin black lines).
- Verdict: edge is not a non-literal guide — it is a literal guide in a different colour. Do not use edge. The only guides that pass are ones with no character shapes at all (room-only) or no guide at all.

### V10 — Lane A composed first frame — RENDERED, HARD CUT GONE
- First frame: `v10-composed-first-frame.png` — frame 97 (t=4s) of the P0-A1 output, Kate at the desk with hands on the dial, snow window, lamp, radio. Same P0-A1 prompt, same audio (Piper kristin), same seed 2801, 141 frames, 704x1280.
- Command: `tools/minimax_speech.py submit --name phase0-a1-v10-composed` (absolute paths — the tool resolves relative --image from its own cwd, not the repo root; first relative attempt failed "Image must be an existing PNG").
- Prompt ID: 522a7ee2-64c1-44e6-9ec1-fe1a83e30bbc. Execution 1794739633659-1794740425290, 13m12s (same as P0-A1's 13m16s — no warm speed-up on the 141-frame speech path).
- Output: `comfy-local/output/minimax-speech/phase0-a1-v10-composed_00001_.mp4` (5.875s, 704x1280, 141f)
- Motion: ONE continuous shot — Kate at the desk from frame 1, same framing throughout, no scene jump, no hard cut at ~3s. Head turns slightly toward the dial (f03 in profile).
- Character: EXCELLENT — same Kate throughout.
- Lip sync: visually in step (f01 mouth open speaking, f03 eyes down / mouth closed at a pause, f05 mouth open mid-word, eyes to camera). Same 4/5 as P0-A1 by inspection; audio is the same Piper line through the H3 audio VAE.
- Verdict: PASS. The composed-first-frame fix works. Lane A recipe: first frame = the storyboard panel (character IN the set), never a bare portrait.

## Not run, with reasons (evidence from the variants that did run)
- V2 depth: guide as rendered was flat/unusable (range 50-59, stdev 1.8 — background infinity compresses it). A Math-node re-render ((11-depth)/6) was planned but not done: V3 and V11 already pass Barrett's bar, and V4/V12 prove any guide containing character shapes is copied literally — a depth map of the capsules would be copied as foggy shapes, not as clean blocking. Depth only matters if a character-shaped guide is ever needed again; it is not.
- V6 cap 5 + bridge alpha 0.05: not run. The guide still contains the orange egg; V1/V4/V5b prove AddGuide copies any character shape literally for the anchored duration — cap 5 would still show the egg for ~0.2s plus the f01 flash. It cannot pass Barrett's bar.
- V7 chunked (two 22f anchors): not run. More anchoring = more literal copy — V5b proved that. It would be worse than B1b, not better.
- V8 Wan 2.2 TI2V-5B: NOT run in this pass. Model IS installed (wan2.2_ti2v_5B_fp16.safetensors + wan2.2_vae.safetensors, text encoders present; template at E:\SwarmUI\Output\atmosphere-lab\sam3-window-mask-test\SAM3_Wan5B_NeonWindowLoop_ComfyUI.json). It is a whole new lane (different graph, no AddGuide equivalent), not a Lane B fix, and H3 already has two passing variants. Open follow-up if Barrett wants a second model lane.
- V9 textured / white-clay guide: not run. V4 proved solid shapes are copied literally whatever the colour — a white-clay capsule would be a white egg. The textured render came out overexposed white clay anyway.
- LTX-2.3 FP8: NOT installed anywhere on the box (only blueprints / API nodes). Recorded as missing; do NOT download (~16GB) without Barrett's approval.

## Recommendation (updated Lane B)
- Default for a moving two-character shot: **no guide at all (V11)** — prompt + reference images, 4m04s, cleanest output, photoreal from frame 1. Use it when the blocking can be prompt-driven.
- When the exact Blender camera path / door location must be preserved: **room-only guide (V3)** — camera + set only, no characters in the guide, 22-frame cap, 5m10s. Keeps B1b's door/blocking and removes the artifact entirely.
- Never again: full character guide (B1b/V1), silhouette guide (V4), edge guide (V12), start/end anchors (V5b), or any guide containing character shapes — AddGuide copies them literally, in whatever colour/shape they are.
- Lane A: always use a composed first frame (V10) — character in the set, never a bare portrait.
