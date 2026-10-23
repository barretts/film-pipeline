# P7-T01 · Captions (MOSS word timings)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P6-T02, P6-T06 | MOSS-Transcribe-Diarize | 20–40 min | — |

**Goal:** a caption file with word timings for every voice-over line and every talking line, made by MOSS as in the post. Captions are on-screen text, so they also pass the facts check.

## Steps
1. **Load MOSS.** Use only the entries in the `vo` and `dialogue` sections of `edit/picks.json`. **Don't glob folders**, which also hold takes and other files.
2. **For each pick**, call `transcribe` with word or segment timestamps. Write `captions/<id>.json`, with times local to the clip, in seconds:
   ```json
   {"id": "v03", "text": "...", "words": [{"w": "Every", "start": 0.12, "end": 0.41}]}
   ```
   If only segment times exist, spread the words across each segment's span, weighted by word length, and set `"timing": "estimated"`.
3. **Compare** each caption's text with its approved line, using `qa_take.py`'s normalization. On a mismatch, keep the **script text** aligned to MOSS's timing, and note it in the task log.
4. **Truth check.** Write all caption texts to `captions/all_text.txt`, then run:
   ```bash
   .venv/Scripts/python tools/facts.py check --file captions/all_text.txt
   ```
5. Unload.

## Outputs
- `captions/<id>.json` for every picked voice-over and dialogue line.

## Done when
- [ ] There is one caption file per pick.
- [ ] Each caption's text matches its line, or was replaced with a note.
- [ ] The facts check passes.

## STATUS line
`P7-T01 DONE · 17 caption files, word-level timings, facts OK` (example)
