# V11 first-frame investigation — Barrett was right, the fix-run report was wrong

Date: 2026-11-15. File: `F:\film-pipeline\comfy-local\output\phase0\V11-no-guide_00001.mp4`
(124 frames, 24 fps, 5.167 s, 1280x704, h264). The `-audio` version is
byte-identical in video: frame 0 and frame 9 md5-match the plain version.

## What frame 0 actually looks like

Barrett: "why is the first frame of the v11 have Kate as a grey polygon person shape?"
Verified by direct frame extraction (ffmpeg `select eq(n,N)`, viewed frame by frame):

- **Frames 0–8: Kate is a flat grey/white faceted polygon** — untextured, hard
  polygon edges on head, neck, torso, arm extended to the dial. Seated at the
  desk, frame right, in profile. The rest of the frame is already photoreal:
  the radio room, snow window, lamp, radio racks, and James in the door
  window in his orange suit.
- **Frame 9: transitional** — hair/face start gaining texture, jacket still
  flat light grey.
- **Frame 10: mostly photoreal** — navy jacket, hair, face in profile, still
  slightly soft/ghostly.
- **Frame 24 (t=1s): fully photoreal Kate** — navy jacket, cream sweater,
  lanyard, silver-streaked hair. She stays photoreal through frame 123,
  looking up at James at the desk.

So the grey polygon persists **frames 0–8 inclusive, ~0.38 s**, not just
frame 0. The fix-run claim "photoreal from frame 1" is **wrong**. The
fix-run scorer sampled at 1 fps (their f01/f03/f05 are t=0/2/4 s) and
evidently never looked at frames 0–8; the ComfyUI thumbnail
`V11-no-guide_00001.png` saved alongside the video IS frame 0 and shows
the grey Kate — this is not a player-thumbnail artifact and not an
extraction artifact (thumbnail md5-independent, same image).

## Was any guide wired into V11? No — verified in the submitted graph

`comfy-local/phase0-V11-no-guide-submission.json`, Prompt ID
91bdcc83-59dd-4d85-a4e4-27349c0ef29a, seed 5002, mode `none`:

- **No AddGuide node, no VHS_LoadVideo node.** `positive` = bridge node 160
  only. The guide file (`jobs/phase0-rigid-llm/guide/p0-b1-guide.mp4`) is
  listed in the submission metadata as the default `--guide` argument and
  was copied to `comfy-local/input`, but it is **not referenced by any node
  in the submitted graph**.
- Inputs actually fed: prompt (V1 prompt-map text), Kate portrait
  `series/characters/kate/portrait.png` (photoreal), James portrait
  `series/characters/james/portrait.png` (photoreal), silence audio,
  `MiniMaxH3ReferenceToVideo` (node 157) + `SenseNovaH3DistilledBridge`
  alpha 0.15 (node 160), 4-step turbo sampler (`BasicScheduler` steps 4,
  denoise 1.0, sampler `er_sde`, turbo 4-step LoRA).
- The base graph's node 5 (`LoadImage minimax-test-anime.png`, first-frame
  input to the original ImageToVideo node) was **popped** by
  `lane-b-variant.py`; node 142 (its resize) is orphaned and consumed by
  nothing. No hidden first-frame image.
- **Mismatch worth noting:** the V1 prompt still says "<Video 1> is an
  untextured basic-shape 3D blockout. Follow its exact camera movement…"
  and "matching them to the blockout figures by position and action" —
  even though no Video 1 was fed in V11. The model was told a blockout
  exists that it never saw.

So the grey Kate is **not** a leftover guide PNG, not a wiring mistake
in V11, and not a thumbnail artifact. It is in the generated video itself.

## Is it V11-only? No — it is the same temporal morph, with different elements lagging

- **B1b frame 0:** literally the raw Blender guide — flat grey room, tan
  door, orange capsule James centre. Frame 24: James photoreal at the
  door, orange egg still centre, room still flat. Frame 48: room partly
  photoreal, egg still centre. Frame 96: room photoreal, egg STILL centre.
- **V3 frame 0:** literally the raw room-only guide — flat empty grey room,
  tan door. Frame 24: James photoreal peeking at the door, room still flat.
  Frame 48: room partly photoreal. Frame 96: fully photoreal, no egg.
- **V11 frame 0:** room + James already photoreal, Kate alone grey polygon.
  Frames 9–10 she resolves; frame 24 fully photoreal.

Pattern across all three: this H3 setup (4-step turbo, bridge alpha 0.15)
**morphs from its conditioning / initial latent to photoreal over the
first ~0.4–2 s**, with different elements resolving at different rates.
In guided variants the starting state IS the guide, so the morph is
visible as the whole scene. In V11 there is no guide, so the starting
state is the model's own untextured prior — and Kate, the largest and
most complex figure in frame (face/hair in profile, at the frame edge),
is the slowest element to resolve, taking 9 frames. James (simple orange
suit, small in frame) resolves immediately.

Two contributing factors, in order of evidence:
1. **Model cold-start / early-frame under-resolution** (best explanation,
   consistent with all three variants). The 4-step sampler has very few
   steps to texture a complex face; the first temporal positions lag.
2. **The V1 prompt tells the model a blockout exists** ("untextured
   basic-shape 3D blockout", "blockout figures are uncolored") with no
   video supplied. The model may be hallucinating the blockout it was
   told about — rendering Kate as the grey mannequin first, then letting
   the reference portrait take over. This is inference, not proof, but it
   fits Kate specifically being the grey figure, and it is testable by
   re-running V11 with a prompt that never mentions a blockout.

## Fix (proposed — do NOT re-render without Barrett's go-ahead)

Cheapest, in order:
1. **Trim the first 10 frames (~0.42 s)** — or start the shot at frame 10.
   The remaining 114 frames are clean and photoreal, motion intact.
   Zero re-render cost; loses 0.4 s of the walk-in.
2. **Use a composed photoreal first frame (V10 recipe)** — feed a
   photoreal Kate-at-desk frame as the first-frame anchor, as Lane A V10
   did, instead of starting from noise/portraits only.
3. **Rewrite the V11 prompt to remove all blockout language** — no
   "<Video 1>", no "blockout figures", just "James enters left, crosses
   to Kate at the desk right, camera dollies right". Test whether the
   grey mannequin disappears; if it does, cause (2) above is confirmed.
4. If (3) does not fix it, the cause is (1) alone — then the fix is (1)
   trim, or more sampler steps (costs render time; the 4-step turbo is
   what makes V11 fast at 4m04s).

## What this changes about the fix-run verdict

- V11 is still the cleanest *overall* shot and still has zero guide
  pixels by construction — but it is **not** "photoreal from frame 1".
  It is photoreal from frame ~10. That matters for any edit that opens
  on this shot: the first 0.4 s cannot be used as-is.
- V3's claim "by f03 the room is fully photoreal" is also overstated:
  at t=2 s (frame 48) V3 is only partly photoreal; it is fully photoreal
  by ~frame 96 (t=4 s). The 1-fps sampling in the fix run understated
  the morph duration in both variants.
- Standing rule still holds: never a guide with character shapes. The
  new wrinkle is that even with NO guide, the first ~10 frames can
  carry an untextured-figure artifact, so every variant needs a
  frame-0–10 check, not a 1-fps check.

## Frame evidence saved here

`results/v11-frames/` (copies of the frames viewed):
- `v11-f0.png`, `v11-f5.png` — grey polygon Kate
- `v11-f9.png`, `v11-f10.png` — resolving
- `v11-f24.png` — fully photoreal
- `v3-f0.png`, `v3-f24.png`, `b1b-f0.png`, `b1b-f24.png` — same morph in
  the guided variants (guide → photoreal)
