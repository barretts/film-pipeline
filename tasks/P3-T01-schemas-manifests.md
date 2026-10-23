# P3-T01 · Schemas, validator, manifests

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 2 scripts) | P2-T15 | none | 60–90 min | — |

**Goal:** catch broken script, EDL and batch files early, and make every batch resumable across sessions.

**Read first:** P3 phase file (coding standards); `templates/shot_list.schema.json`, `edl.schema.json`, `manifest.schema.json`.

## Spec: `tools/validate.py`
- **Usage:** `validate.py <kind> <file>`, where kind is `shot_list`, `edl`, `manifest` or `picks`. It loads `templates/<kind>.schema.json` and prints `OK <file>`, or up to 20 `path: message` errors. Exit 0 or 1.
- **Extra checks for `shot_list`:**
  - ids are unique;
  - every `vo_lines[].shot` and `sound_cues[].shot` exists;
  - total `duration_s` is within ±10% of `target_seconds`;
  - `motion` and `hero` shots are ≤ 4.8 s, `talking` shots are ≤ 4.8 s unless MODELS.md allows longer clips, and `still` shots are ≤ 6 s;
  - each VO line is ≤ 12 words with `max_seconds` ≤ 4.5, and talking lines are ≤ 10 words;
  - `talking` shots have a `talking_line`;
  - `feature_id` values exist in `script/features.json` (when that file exists).
- **Extra checks for `edl`:**
  - video items are sorted, and consecutive items overlap **only** by the incoming item's dissolve duration;
  - `duration_s` is within ±5% of `target_seconds` in `script/shot_list.json` (when that file exists);
  - the last end is ≤ `duration_s`;
  - title, subtitle and label overlays have a `fact_ref`;
  - every referenced file exists.
- **Extra checks for `manifest`:** item ids are unique; `done` and `picked` items have outputs that exist.
- **Extra checks for `picks`:**
  - every file exists;
  - every shot pick has `type`, `fps`, `width` and `height`;
  - when `script/shot_list.json` exists, every shot, voice-over line and cue in it has a pick.

## Spec: `tools/manifest.py`
- **Commands:**
  - `new <file> --name N --model M --tool T [--defaults JSON]`
  - `add <file> --id ID [--shot S] --params JSON`
  - `next <file>`: prints the first `todo` item as compact JSON (≤ 15 lines), or `none`.
  - `set <file> <id> key=value …`:
    - plain assignments: `status=done`, `job_id=abc`, `notes="…"`;
    - list appends: `outputs+=path`, `mcp_seq+=42`;
    - counters: `attempts+=1`;
    - file values: `qa=@file.json`.
  - `summary <file>`: counts per status, plus the ids of failed and rejected items.
- **Writes:** every write is atomic (temp file, then replace) and is validated against the schema afterwards. An invalid write is refused and the file stays unchanged.

## Steps
1. Write both scripts.
2. Test the manifest helper with a temp manifest (`tests/samples/m.json`):
   - walk one item through `todo → queued → done`;
   - check that an invalid status is refused;
   - check that `next` and `summary` output is correct.
3. Hand-write `tests/samples/shot_list_min.json` (2 shots, 1 VO line, 1 cue), `tests/samples/edl_min.json` (2 clips from the fixtures, joined by a dissolve) and `tests/samples/picks_min.json`, then run `validate.py` on each to an OK. Break one field on purpose and confirm the error message is clear.
4. Record all test commands and results in the task log.

## Outputs
- `tools/validate.py`, `tools/manifest.py`, samples in `tests/samples/`.

## Done when
- [ ] Every test passes, and invalid input is rejected with readable messages.

## STATUS line
`P3-T01 DONE · validate + manifest tools tested on samples` (example)
