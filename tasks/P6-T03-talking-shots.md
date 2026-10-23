# P6-T03 · Talking shots (LTX-2.5)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P6-T02 | LTX-2.5, then HTDemucs/MOSS for gating | 1–3 h | — |

**Goal:** every talking shot shows lips that match a QA-passed line in her voice.

**Read first:**
- STATUS › Decisions: talking strategy A or B
- TOOLS.md: LTX audio input, max frames
- MODELS.md › Production settings

## Steps
1. **Build `jobs/talking.json`**, up to 2 takes per talking shot (`<shot>_talk_t1`, `_t2`). Params:
   - start frame: `<ROOT>/stills/<shot>_still.png`
   - size and fps: 896×512 at 24 fps (or MODELS.md production settings), with a seed
   - frames: the smallest 8n+1 ≥ 24 × max(shot `duration_s` + 0.2, line seconds + 0.6)
   - prompt: the shot's `motion_prompt` + the voice description
     - **strategy B:** also include the line in quotes
   - **strategy A:** `audio` = `<ROOT>/audio/dialogue/<shot>_dlg.wav` (picked in P6-T02)
2. **Generate all takes in one batch.** Load LTX-2.5, queue the items, poll as in CONTEXT §8, and download each take to `video/candidates/<id>.mp4`. Then **unload LTX-2.5**.
3. **Gate the batch.**
   - **Strategy A:**
     1. Extract the audio and transcribe it with MOSS. The line must match exactly.
     2. Check the mid-frames on a contact sheet.
     3. Ask the human to spot-check lip sync on the first clip.
   - **Strategy B:**
     1. Extract the audio and run HTDemucs to get the vocals.
     2. Run MOSS, then `qa_take.py` against `audio/ref/voice_ref.wav`.
     3. A PASS is kept.
   - **Retries:** reload LTX-2.5 only for the failed shots, as one batch, with new seeds. Allow at most 4 attempts per shot.
4. **Fallback C**, if B still fails after 4 attempts:
   1. Keep the best video.
   2. Generate the line with Breeze and gate it as in P6-T02.
   3. Use that take as the dialogue, and record "loose lip sync" for the shot.
5. **Picks.**
   - Copy the video to `video/talking/<shot>_talk.mp4`.
   - Dialogue audio (48 kHz) lives at `audio/dialogue/<shot>_dlg.wav`:
     - strategy A: the driving take already picked in P6-T02;
     - strategy B: the isolated vocals of the picked clip;
     - fallback C: the Breeze take.
   - Mark the take `picked`. Add the video to `edit/picks.json` under `shots`, with `type` talking, `fps`, `width`, `height`, `duration_s`, `source` and `mcp_seq`. Add the dialogue under `dialogue`.

## Outputs
- Picked talking clips and dialogue WAVs
- `jobs/talking.json`
- Updated picks

## Done when
- [ ] Every talking shot has a picked clip and dialogue that passed the gate. Fallback-C shots are noted.

## STATUS line
`P6-T03 DONE · 4/4 talking shots; strategy A; 1 retake` (example)
