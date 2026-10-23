# P5-T02 · Production prompt (~2,500 words)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P5-T01 | writer (Qwen3.8-27B) | 30–60 min | — |

**Goal:** have the local writer expand the brief into a detailed production prompt, as in the post, bound by the truth rule and this PC's limits.

**Read first:** `brief.md`; `script/features.json` (titles + lines only); CONTEXT §4–5.

## Steps
1. Load the writer (default quant) with context 32k. Use `reasoning_effort` medium. If the reply contains a thinking or reasoning block, strip it before saving; only the final answer goes into the file.
2. Call `chat` once, passing all of the following. Keep the inputs under about 1,800 words in total.
   - the full `brief.md`;
   - the feature list (id, title, line, metaphor);
   - the production limits:
     - shot types and their models: motion = Wan2.2-5B, ≤ 4.8 s, 1280×704; hero = Wan2.2-A14B, ≤ 4.8 s, at most 6 shots (or the MODELS.md limit); talking = LTX-2.5, ≤ 4.8 s, at most 5 shots; still = held image, ≤ 6 s;
     - voice-over: ≤ 12 words and ≤ 4.5 s per line;
     - 18–22 shots, about 75 s in total;
   - the **truth rule**: "Never state numbers or feature names except those given; mark any on-screen fact as FACT(<feature id or facts key>)";
   - the required output: these eight sections, about 2,500 words in total:
     1. Visual language and palette
     2. Character bible (face, hair, coat, posture, voice description)
     3. Act structure with timings
     4. Reveal beats, one per feature
     5. The classroom loss-curve beat
     6. Sound design and music direction (with a lyric theme)
     7. Typography and title cards
     8. Do and don't list
3. Save the reply to `script/production_prompt.md`. Note its word count in the task log; don't re-read the whole file.
4. Check it with grep and a quick skim of the headings:
   - word count is 2,000–3,000;
   - all 8 headings are present;
   - every `FACT(...)` names a known feature id or facts key;
   - no stray numbers appear in title-card text.
5. If a check fails, call `chat` once more with the specific fix requests. Then unload.

## Outputs
- `script/production_prompt.md`.

## Done when
- [ ] All the checks in step 4 pass.

## STATUS line
`P5-T02 DONE · 2,480-word production prompt, 8 sections, FACT refs valid` (example)
