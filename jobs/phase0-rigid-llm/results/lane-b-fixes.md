# Lane B fix run — local only, no cloud. Measured on file-cabinet, 2026-11-15. Do not invent numbers.

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

### V3 — room-only guide
- Guide: `guide/room-only.mp4` — Workbench, characters hidden. Frame 60 verified: room, door, desk, lamp only (small ball at desk is the lamp).
- Status: TBD

### V4 — white silhouettes on black
- Guide: `guide/silhouette.mp4` — Workbench FLAT, characters white, room black. Frame 60 verified: clean white egg shapes on black, no orange, no color.
- Status: TBD

### V5 — start/end AddGuide only
- Mode: start_end in lane-b-variant.py — 1-frame first guide frame at 0, 1-frame last at 123, chained AddGuide nodes.
- Status: TBD

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

## Guide-format notes (Blender 5.2.2)
- Engine enum is `BLENDER_EEVEE`, not `BLENDER_EEVEE_NEXT`.
- Compositor node tree is `scene.compositing_node_group` (new node group), not `scene.node_tree`; Composite node is `NodeGroupOutput`.
- `CompositorNodeMapRange` does not exist in 5.2. Use Math nodes: (11 - depth) / 6, clamped.
- `scene.eevee.use_soft_shadows` does not exist; use `scene.eevee.use_shadows`.
- Workbench variants render ~18s; EEVEE variants ~63-68s for 124 frames.
