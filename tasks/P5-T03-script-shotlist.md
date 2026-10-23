# P5-T03 · ✋ Script + shot list

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT → HUMAN approves | P5-T02 | writer (Qwen3.8-27B) | 45–90 min | ✋ yes |

**Goal:** the human approves a locked, valid `script/shot_list.json` (shots, voice-over lines, sound cues, music) and `script/lyrics.txt`.

**Read first:**
- `templates/shot_list.schema.json` (field names only)
- `script/features.json`
- MODELS.md › Production settings (any hero-shot limit or changed clip lengths)

## Steps
1. Load the writer, in instruct mode with no thinking trace. Call `chat` with `production_prompt.md`, the features (id + title) and the schema field list. Ask for **JSON only** that meets these constraints:
   - **Shots:**
     - 18–22 shots, totalling 70–80 s;
     - `motion` and `hero` shots ≤ 4.8 s; `talking` shots ≤ 4.8 s (or longer only if the clip length in MODELS.md allows); `still` shots ≤ 6 s;
     - at most 6 `hero` shots (fewer if MODELS.md says so), at most 5 `talking`, at most 3 `still`; the rest `motion`;
     - every shot has `has_character` and a fixed `seed` (shot number × 100);
     - every feature appears in ≥ 1 shot via `feature_id`; acts run open → reveal → classroom → close.
   - **On screen:**
     - one classroom shot has `on_screen: [{"fact_ref": "training.loss_curve", "style": "chalk_curve"}]`;
     - title cards use `fact_ref` keys only, such as `features.<id>.title`, `server.product` (closing card) or other `facts.json` keys;
     - nothing on screen is free text.
   - **Lines:**
     - voice-over lines ≤ 12 words, each with `delivery` and `max_seconds` (≤ 4.5);
     - talking lines ≤ 10 words.
   - **Sound:**
     - 8–14 sound cues, each with `shot`, `offset_s` and `gain_db`, including 1–2 drones of 15–20 s;
     - `music` with `style`, `target_seconds` (= total + 4), `start_s`, `fade_in_s` and `fade_out_s`.
2. Call `chat` a second time for the lyrics: verse and chorus sections matching the music length, on the theme in the production prompt. Save them to `script/lyrics.txt`.
3. Save `script/shot_list.json` with `character_master` set to `stills/character_master.png`, then validate it:
   ```bash
   .venv/Scripts/python tools/validate.py shot_list script/shot_list.json
   ```
4. **Truth checks.**
   - Write every voice-over and talking line to `script/lines.txt`, one per line, then run:
     ```bash
     .venv/Scripts/python tools/facts.py check --file script/lines.txt
     ```
   - `features.*.title` and `server.*` refs must resolve now.
   - `training.*` and `export.*` refs stay **pending** until P6-T09. List them in the task log.
5. Write a review table of ≤ 30 lines into `logs/tasks/P5-T03.md`: shot · type · seconds · feature · VO/talking line (short).
6. **[HUMAN] ✋** Ask: "Approve this script? (yes / change …)". Revise until approved, at most 3 rounds.
7. Unload the writer.

## Outputs
- `script/shot_list.json` (valid), `script/lyrics.txt`, `script/lines.txt`, the review table.

## Done when
- [ ] Validation is OK.
- [ ] The step 1 constraints hold.
- [ ] The line facts check passes.
- [ ] The human approved.

## STATUS line
`P5-T03 DONE · 20 shots, 76 s, 13 VO lines; approved` (example)
