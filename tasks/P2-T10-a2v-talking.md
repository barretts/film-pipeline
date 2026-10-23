# P2-T10 · Audio-driven talking test (optional)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ human watches) | P2-T09 | LTX-2.5 | 20–60 min | — |

**Goal:** choose how talking shots are made in production.

**Condition:** run this only if P2-T06 found that `generate_video` accepts an **audio input** for LTX-2.5. If it doesn't:
- set this task to **SKIPPED**;
- add to Decisions: `Talking strategy B: native LTX audio + QA gates`;
- stop here.

## The two strategies
- **A, audio-driven:** a Breeze take that passed QA drives LTX-2.5. The voice is the same everywhere, and the lips follow the given audio.
- **B, native audio:** LTX-2.5 speaks the line itself, as in the post. Takes are gated on transcript and pitch, and the voice can drift between shots.

## Steps
1. Load LTX-2.5. Call `generate_video` and save the result to `tests/fixtures/talk_a2v.mp4`:
   - start frame `<ROOT>/tests/fixtures/portrait.png`; seed 4002; 896×512, 24 fps;
   - audio `<ROOT>/tests/fixtures/clone_t1.wav` (or the best take);
   - frames: the smallest 8n+1 that is ≥ the take's duration × 24;
   - prompt:
     > she speaks the line softly, subtle head and eye movement, 2D hand-painted
2. Run `ffprobe`. The clip should have audio, and its length should match the take within 0.2 s.
3. **[HUMAN]** Watch `talk_a2v.mp4` and answer: "Are the lips believably in sync? yes/no"
4. Record the decision:
   - yes → `Talking strategy A: audio-driven`;
   - no → `Talking strategy B`.

   Unload.

## Outputs
- `tests/fixtures/talk_a2v.mp4`
- Talking strategy recorded in Decisions

## Done when
- [ ] The talking strategy (A or B) is recorded. This is required even if the task was SKIPPED.

## If it fails
- **The audio parameter is rejected:** treat it as unsupported and use strategy B.

## STATUS line
`P2-T10 DONE · strategy A (lips sync with Breeze audio)` (example)
