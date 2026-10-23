# P2-T07 · Voice isolation: HTDemucs

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T06 | HTDemucs (small) | 10–20 min | — |

**Goal:** pull a clean voice stem out of the talking clip's audio. This is how the post got the voice it cloned later.

## Steps
1. Call `generate_audio` in **separate** mode with model HTDemucs on `<ROOT>/tests/fixtures/talk_native.wav`. Ask for the stems as links.
2. Download the **vocals** stem. Resample it to 48 kHz stereo `pcm_s24le` and save it as `tests/fixtures/talk_vocals.wav`.
3. Sanity check: compare the loudness of the input and the vocals:
   ```bash
   ffmpeg -hide_banner -i tests/fixtures/talk_native.wav -af volumedetect -f null - 2>&1 | grep mean_volume
   ffmpeg -hide_banner -i tests/fixtures/talk_vocals.wav -af volumedetect -f null - 2>&1 | grep mean_volume
   ```
   For a speech-only clip, the vocals should be within ~3 dB of the input.
4. Unload if it was loaded as its own model. Record seconds per clip in MODELS.md › Separation.

## Outputs
- `tests/fixtures/talk_vocals.wav`

## Done when
- [ ] The vocals stem exists, is 48 kHz stereo, and passes the loudness sanity check.

## If it fails
Use the demucs CLI fallback, from MODELS.md:
```bash
.venv/Scripts/python -m pip install -q demucs
.venv/Scripts/python -m demucs --two-stems=vocals -n htdemucs -o tests/fixtures/demucs tests/fixtures/talk_native.wav
```
Take `tests/fixtures/demucs/htdemucs/talk_native/vocals.wav` and resample it as in step 2. Record "separation via CLI" in Decisions.

## STATUS line
`P2-T07 DONE · vocals stem clean, 6 s per clip` (example)
