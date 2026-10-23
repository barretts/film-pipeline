# P4-T01 · Pilot script + shot list

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P3-T02, P3-T06 | writer (Qwen3.8-27B) | 20–30 min | — |

**Goal:** a valid 15-second, 3-shot script, written by the local writer model, to drive the end-to-end pilot. All pilot files live under `pilot/`.

**Read first:** P4 phase file (pilot spec); `brief.md`; CONTEXT §5.

## Steps
1. Create the pilot folders:
   ```bash
   mkdir -p pilot/script pilot/stills pilot/video pilot/audio/vo pilot/audio/dialogue pilot/audio/music pilot/audio/sfx pilot/captions pilot/edit pilot/mix
   ```
2. Refresh the facts and print only the tool names (≤ 20 lines):
   ```bash
   .venv/Scripts/python tools/facts.py build
   .venv/Scripts/python tools/facts.py get tools_order
   ```
3. Load the writer (default quant from Decisions). Call `chat` in **instruct mode, with no thinking trace**, using a prompt of ≤ 500 words that contains:
   - the brief's tone and style, summarized in ≤ 120 words;
   - the shots:
     - s01: talking, 4.8 s, one spoken line of ≤ 10 words;
     - s02: motion, 4.8 s, one voice-over line of ≤ 12 words with `max_seconds` ≤ 4;
     - s03: hero, 4.8 s;
   - for each shot, a still prompt and a motion prompt, painterly 2D in the brief's palette, with `has_character` true or false;
   - 8 lyric lines in 2 sections, a music style, 2 SFX cues and 1 drone, each cue with `shot`, `offset_s` and `gain_db`;
   - the field names of `templates/shot_list.schema.json`, written as a list in the prompt, and **"Return JSON only."**
4. Save the reply to `pilot/script/shot_list.json` and fix small syntax problems yourself. Then set:
   - `character_master`: `tests/fixtures/portrait.png`;
   - s03 `on_screen`: `[{"fact_ref": "tools.generate_video.name", "style": "title"}]`;
   - `music.lyrics_file`: `pilot/script/lyrics.txt` (write the lyrics there);
   - `target_seconds`: 14.4.
5. Validate the shot list, then check every spoken line against the facts:
   ```bash
   .venv/Scripts/python tools/validate.py shot_list pilot/script/shot_list.json
   ```
   Write the VO line and the talking line to `pilot/script/lines.txt`, one per line, then:
   ```bash
   .venv/Scripts/python tools/facts.py check --file pilot/script/lines.txt
   ```
6. Unload the writer.

## Outputs
- `pilot/script/shot_list.json`, `pilot/script/lyrics.txt`, `pilot/script/lines.txt`.

## Done when
- [ ] Validation prints OK.
- [ ] The line facts check passes.
- [ ] Every word and duration limit in step 3 holds.

## If it fails
- **The writer returns prose instead of JSON:** run it again with a stricter instruction and a one-shot example using 2 fields.
- **Still failing after 2 retries:** write the JSON yourself, using the writer's prose as the content.

## STATUS line
`P4-T01 DONE · pilot shot list valid (3 shots, 14.4 s)` (example)
