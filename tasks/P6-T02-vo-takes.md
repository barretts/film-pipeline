# P6-T02 · Voice-over takes + QA gate

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P6-T01 | Breeze-TTS-2 + MOSS (co-loaded if ≥ 2 GB free) | 1–2 h | — |

**Goal:** one approved take that passed the QA gate for every voice-over line. Under talking strategy A, the same for every talking line.

## Steps
1. **Build `jobs/vo.json`** with `tools/manifest.py`:
   - 3 takes per `vo_lines[]` entry, ids `<v>_vo_t1` … `t3`;
   - **strategy A only:** 3 takes per talking shot's `talking_line`, ids `<shot>_dlg_t1` … `t3` (kind `dlg`, so they go to the dialogue bus, not the voice-over bus);
   - params for each take:
     - `text`: the line, with an optional inline event such as `(sigh)`, used sparingly;
     - `instruction`: the line's `delivery` (voice direction, cfg 4);
     - `reference_audio`: `<ROOT>/audio/ref/voice_ref.wav`;
     - `reference_text`: the contents of `audio/ref/voice_ref.txt`;
     - `seed`.
2. **Load** Breeze-TTS-2, plus MOSS if it fits.
3. **Generate and gate**, at most **24 takes (8 lines) per session**. For each line:
   1. Generate its 3 takes as `audio/vo/<id>.wav` (talking lines: `audio/dialogue/<id>.wav`).
   2. Transcribe each take and save `<id>.transcript.json` next to it.
   3. Run the gate:
      ```bash
      .venv/Scripts/python tools/qa_take.py --audio <file> --expected "<line>" --transcript <file>.transcript.json --ref audio/ref/voice_ref.wav --json-out <file>.qa.json
      ```
   4. Record the result:
      ```bash
      .venv/Scripts/python tools/manifest.py set jobs/vo.json <id> qa=@<file>.qa.json status=done
      ```
      Use `status=rejected` instead of `status=done` for a FAIL.
4. **No PASS yet:** add 3 more takes with new seeds and gate them. Stop at **9 takes** per line.
5. **Pick per line.** Choose the **shortest PASS whose duration ≤ `max_seconds`**. If two are within 0.2 s of each other, prefer the smaller |semitone diff|.
   - Voice-over: copy to `audio/vo/<v>_vo.wav`.
   - Strategy A talking lines: copy to `audio/dialogue/<shot>_dlg.wav`.
   - Resample to 48 kHz and mark the take `picked`.
   - Add it to `edit/picks.json` under `vo` (or `dialogue`), with `file`, `duration_s`, `source` (`jobs/vo.json#<id>`), `qa` and `mcp_seq` (from `mcp_report.py --seq-only`).
6. **Still no PASS after 9 takes:**
   - shorten or rephrase the line, keeping its meaning, and record the change in Decisions and in `shot_list.json`;
   - **or**, with the human's OK, allow 2.0 semitones for that line only.
7. Unload.

## Outputs
- `audio/vo/<v>_vo.wav` for every line, plus strategy-A dialogue picks
- `jobs/vo.json`
- `edit/picks.json` (`vo` and `dialogue` sections)

## Done when
- [ ] Every line has a picked take that passed QA and is ≤ `max_seconds`.
- [ ] `manifest.py summary jobs/vo.json` shows no `todo`.

## STATUS line
`P6-T02 DONE · 13/13 lines PASS; 7 takes rejected` (example)
