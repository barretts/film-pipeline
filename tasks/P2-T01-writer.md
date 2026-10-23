# P2-T01 · Writer: Qwen3.8-27B

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T04, P1-T06 | Qwen3.8-27B GGUF | 30–60 min | — |

**Goal:** confirm the writer runs with RAM offload, measure tokens/s for both quants, and pick the default.

**Read first:** P2 phase file (standard procedure); TOOLS.md (`load_model`, `chat`); MODELS.md › Writer.

## Steps
1. **Standard procedure, steps 1–3.** Load `unsloth/Qwen3.8-27B-GGUF`, variant `UD-Q4_K_XL`, context 32768.
2. Call `chat` in instruct mode (thinking off, or `reasoning_effort` none or low), with temp 0.7, top_p 0.8, presence_penalty 1.5:
   - system: "You write vivid, precise screen directions."
   - user: "In 350–450 words, describe one 2D hand-painted, A24-style shot: a dark room, one desk lamp, a woman watching a glowing machine. Present tense, no dialogue."

   Write the reply to `tests/fixtures/writer_sample.md`. **Don't copy the text into your notes.** Record only the word count and the time.
3. Work out tokens/s ≈ (words × 1.33) ÷ the call's duration from `mcp_report.py --last 3`, or use the usage numbers if `chat` returns them.
4. Unload, then repeat steps 1–3 with variant `UD-Q3_K_XL`. Save that reply to `tests/fixtures/writer_sample_q3.md`.
5. Run one short call in thinking mode with `reasoning_effort` low, to confirm the parameter name works. Write it into TOOLS.md.
6. Pick the default:
   - **UD-Q4_K_XL** if it gives ≥ 8 tok/s;
   - otherwise **UD-Q3_K_XL**.

   Record both measurements in MODELS.md and the choice in STATUS › Decisions.
7. Unload.

## Outputs
- `tests/fixtures/writer_sample.md`, `writer_sample_q3.md`
- MODELS.md › Writer row (tok/s, peak VRAM)
- Decision line in STATUS

## Done when
- [ ] Both quants are measured.
- [ ] The default is chosen and recorded.
- [ ] The reasoning parameter is confirmed in TOOLS.md.

## If it fails
- **OOM on load:** drop the context to 16384. Still OOM? Use Q3 only.
- **Under 4 tok/s:** check `studio_status` to confirm offload goes to RAM and not disk, and close other apps. 128 GB should be plenty.
- **The output loops or overthinks:** lower `reasoning_effort`, then try instruct mode.

## STATUS line
`P2-T01 DONE · Q4 9.6 tok/s, Q3 14 tok/s; default UD-Q4_K_XL` (example)
