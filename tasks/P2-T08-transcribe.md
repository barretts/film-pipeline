# P2-T08 · Transcription: MOSS-Transcribe-Diarize

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T07 | MOSS-Transcribe-Diarize 0.9B | 10–20 min | — |

**Goal:** get an exact transcript with timestamps. MOSS is the QA judge for every voice take, and it supplies the exact reference text Breeze-TTS-2 needs.

## Steps
1. Load MOSS-Transcribe-Diarize, or let `transcribe` load it as TOOLS.md describes.
2. Call `transcribe` on `<ROOT>/tests/fixtures/talk_vocals.wav` with timestamps and speaker labels on.
3. From the response, write `tests/fixtures/talk_vocals.transcript.json` yourself:
   ```json
   {"text": "...", "segments": [{"start": 0.31, "end": 2.84, "speaker": "S01", "text": "..."}]}
   ```
4. Compare it with the prompted line "Every feature arrives one at a time." after lowercasing and stripping punctuation, and note match or mismatch. LTX may paraphrase; that's fine here.
5. Record seconds per minute of audio in MODELS.md › Transcribe, and note whether word-level timestamps exist (TOOLS.md). Captions need them in P7-T01.
6. Keep MOSS loaded if P2-T09 comes next and VRAM allows (§3.1). Otherwise unload.

## Outputs
- `tests/fixtures/talk_vocals.transcript.json`

## Done when
- [ ] The transcript JSON exists with segment times.
- [ ] Word-timestamp support (yes or no) is noted.

## If it fails
- **MOSS isn't in Studio:** fall back to MOSS's official repo or `transcribe.cpp` (see the MOSS GitHub). Record it in Decisions; MOSS is required for the QA gates.
- **Speaker labels are present but you don't need them:** ignore them in the text.

## STATUS line
`P2-T08 DONE · MOSS transcript exact; word timestamps: yes` (example)
