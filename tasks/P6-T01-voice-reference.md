# P6-T01 · ✋ Voice reference

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT → HUMAN approves | P5-T05 | LTX-2.5, then HTDemucs + MOSS + Breeze | 45–90 min | ✋ yes |

**Goal:** capture her voice once, as a clean 6–15 s reference with an exact transcript. Every voice-over line is cloned from it. This follows the post, where her voice was pulled from her talking clips and then cloned.

## Steps
1. **Seed text.** Write 2–3 neutral sentences, **20–30 words** in total, in her register. They must not be lines from the script. Example: "I keep the lamp on so the machine can see me. It never sleeps. It only waits for the next thing I ask."
2. **Seed clips.** Load LTX-2.5 and generate 3 clips, seeds 6001–6003:
   - start frame: `<ROOT>/stills/character_master.png`
   - prompt: the voice description from the production prompt's character bible + the sentences in quotes + "quiet room tone, no music"
   - 896×512 at 24 fps
   - **241 frames (~10 s)**, or the maximum recorded in TOOLS.md
   - save as `video/candidates/voiceseed_t1..t3.mp4`

   Unload LTX-2.5.
3. **Per clip:** extract the audio (§10), separate it with HTDemucs (keep the vocals), then transcribe with MOSS using timestamps.
4. **Pick the clearest take.** Look for no bleed, no artifacts, natural rhythm, and a match to the character bible.
   - Trim to **6–15 s** of continuous speech, with 0.2 s padding, and save as `audio/ref/voice_ref.wav` (48 kHz).
   - Write the **exact** transcript of that span to `audio/ref/voice_ref.txt`.
   - If no single clip has 6 s of clean speech, join clean segments from the same take with 0.15 s gaps (ffmpeg concat), and join their transcripts in the same order.
5. **Test the reference.** Load Breeze-TTS-2 and MOSS, and clone one new line from the script. Transcribe it, then run `qa_take.py --ref audio/ref/voice_ref.wav`. The result should be PASS. Save it as `audio/ref/voice_test.wav`.
6. **[HUMAN] ✋** Ask: "Listen to `audio/ref/voice_ref.wav` and `voice_test.wav`. Is this her voice? (yes / redo with: …)".
   - **Redo:** change the voice description and repeat steps 2–5, at most 3 rounds.
   - **Design alternative:** the human may instead choose a voice made with Breeze voice design (an instruction from the character bible). Use the best design take as the reference, with its exact text, and record this in Decisions.
7. Unload.

## Outputs
- `audio/ref/voice_ref.wav` + `voice_ref.txt`
- `audio/ref/voice_test.wav`

## Done when
- [ ] The reference is 6–15 s and its transcript is exact.
- [ ] The test clone passes QA.
- [ ] The human approved the voice.

## STATUS line
`P6-T01 DONE · voice from voiceseed_t2 (11.4 s); test clone PASS; approved` (example)
