# P2-T09 · Voice: Breeze-TTS-2 (clone + design)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T08 | Breeze-TTS-2 (+ MOSS if ≥ 2 GB free) | 20–40 min | — |

**Goal:** clone the generated voice from the talking clip, test voice design as a backup, and confirm MOSS can judge the takes.

## Steps
1. Load Breeze-TTS-2. Keep MOSS loaded too if `studio_status` shows ≥ 2 GB free (§3.1).
2. Prepare the reference:
   1. Use the MOSS segment times to trim `talk_vocals.wav` to continuous speech, with 0.2 s padding at each end. Aim for **6–15 s**. Save as `tests/fixtures/voice_ref_test.wav`.
   2. Write the **exact** transcript of that span to `tests/fixtures/voice_ref_test.txt`. Breeze clones from reference audio plus its exact transcript.
   3. If there is less than 6 s of speech, use what you have and note "short reference". P6-T01 makes the real one.
3. **Clone.** Call `generate_audio` in **clone** mode 3 times, with seeds 1, 2 and 3, and save the results as `tests/fixtures/clone_t1.wav`, `clone_t2.wav` and `clone_t3.wav`:
   - reference audio: `<ROOT>/tests/fixtures/voice_ref_test.wav`
   - reference text: the contents of `voice_ref_test.txt`
   - text: `(sigh) The second feature listens before it speaks.`
4. **Design.** Call `generate_audio` in **speak/design** mode, with the same text and cfg 4, and save to `tests/fixtures/design_t1.wav`. Instruction:
   > A soft, low, slightly husky young woman; calm, secretive, intimate delivery
5. Transcribe all 4 takes with MOSS, and save each as `<name>.transcript.json`. For each, note whether it matches exactly; ignore the `(sigh)` tag.
6. Check one output with `ffprobe` and record Breeze's sample rate (expected 24 kHz).
7. Unload. Record seconds per line in MODELS.md › Voice.

## Outputs
- In `tests/fixtures/`: `voice_ref_test.wav` and `.txt`, `clone_t1.wav`–`clone_t3.wav`, `design_t1.wav`, and their transcripts.

## Done when
- [ ] 3 clone takes and 1 design take exist.
- [ ] At least 1 take transcribes exactly.
- [ ] The reference length and the sample rate are recorded.

## If it fails
- **Clone quality is poor and the reference is short:** note it. P6-T01 builds a 6–15 s reference.
- **Breeze isn't in Studio:** use the Breeze-TTS-2.cpp Windows build (`HoppouAI/Breeze-TTS-2.cpp`, Vulkan, HTTP server). This is a community binary, so get ✋ approval first. Record it in Decisions.

## STATUS line
`P2-T09 DONE · ref 8.2 s; 2/3 clone takes exact; design OK; 24 kHz` (example)
