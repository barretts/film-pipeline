# P3-T02 · QA gate: `tools/qa_take.py`

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P3-T01 | none | 60–90 min | — |

**Goal:** an automatic pass/fail for every voice take, matching the post: if MOSS doesn't transcribe the line exactly, or the pitch drifts from her voice, the take is thrown out.

## Spec
- **Usage:** `qa_take.py --audio TAKE.wav --expected "line" --transcript FILE [--ref voice_ref.wav] [--semitones 1.5] [--json-out PATH]`
  - `--transcript` is a JSON file with `"text"` (as saved from MOSS) or a `.txt` file.
- **Normalization** (applied to both texts):
  - lowercase;
  - remove bracketed and parenthesized tags such as `(sigh)`, `[laugh]` and `[S01]`, and `<…>`;
  - remove timestamps such as `00:01.2`;
  - turn dashes and hyphens into spaces;
  - remove apostrophes and all other punctuation;
  - collapse whitespace.
- **Text result:** `exact_match` (bool) and `wer` (word edit distance ÷ number of expected words).
- **Pitch** (when `--ref` is given):
  - run `librosa.pyin` on 16 kHz mono with fmin 65, fmax 500, and take the median f0 over voiced frames for the take and the reference;
  - `semitone_diff = 12·log2(take/ref)`; `pitch_ok = |diff| ≤ tolerance`;
  - with fewer than 20 voiced frames, `pitch_ok = null` and a reason is given.
- **Other checks:**
  - `duration_s`;
  - `peak_dbfs`: above −0.3 dBFS counts as clipping, which is a fail;
  - leading or trailing silence over 0.8 s gives a warning only.
- **Verdict:** **PASS** only when `exact_match` holds, `pitch_ok` is true (or there's no `--ref`), and nothing clips.
- **Output:** print one line, `PASS|FAIL <file> wer=… st=… reasons=[…]`. Exit 0 for PASS, 1 for FAIL. `--json-out` writes the full result.

## Steps
1. Write the script.
2. Run it on the fixtures `tests/fixtures/clone_t1..3.wav` and `design_t1.wav`:
   - `--transcript`: the matching `.transcript.json`;
   - `--expected`: "The second feature listens before it speaks.";
   - `--ref`: `tests/fixtures/voice_ref_test.wav`.

   Record each verdict and value.
3. Synthetic tests:
   - sine waves at 220 Hz and 233 Hz, made with ffmpeg lavfi `sine`, should give about 1.0 semitone;
   - transcript variants should still match: `"Every feature — arrives, one at a time!"` against `"every feature arrives one at a time"`;
   - a clipped file (volume +20 dB) should fail.
4. Calibrate: if genuine-sounding takes fail pitch at 1.5 semitones, look at the values. Change the default only with a note in Decisions.

## Outputs
- `tools/qa_take.py`; results in the task log.

## Done when
- [ ] The synthetic tests pass.
- [ ] The fixture verdicts are recorded.
- [ ] The tolerance is confirmed or adjusted, with a note.

## STATUS line
`P3-T02 DONE · gate works; fixtures 2 PASS / 2 FAIL; tolerance 1.5 st` (example)
