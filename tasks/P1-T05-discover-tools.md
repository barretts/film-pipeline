# P1-T05 · Discover MCP tools → TOOLS.md

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ optional human step) | P1-T03 | none | 30 min | — |

**Goal:** TOOLS.md describes the real tools and their key parameters in ≤ ~2,500 tokens, so no later task needs to read raw schemas.

**Read first:** TOOLS.md (pre-filled rows).

## Steps
1. **Fill one TOOLS.md row per tool** on the Unsloth server, taken from your own tool list:
   - tick **Confirmed?**;
   - write the parameter names the server uses (only the important ones, plus enums);
   - write short returns/notes.

   Add tools that are missing from the table, and mark absent ones "not present". **Don't paste schemas.**
2. **Capabilities.** Call `studio_status`. Summarize under "Capabilities discovered" in ≤ 6 lines: GPU and free memory, model slots, and the video capabilities (`prompt_hint`, `supports_last_frame`, `references`, `size_presets`).
3. **Media handling.**
   - Find the parameter that returns media as a link instead of inline (e.g. `return_media`) for `generate_image` and `generate_audio`.
   - Record how links are downloaded. Expected: a key-free URL that works with `curl -fsS -o FILE "LINK"` (`-f` so error pages are never saved as media).
   - If a link ever needs auth, don't pass the key yourself. Look for where Studio saves the file on disk and copy it from there.
4. **Job handling.** Note whether `get_job` has a wait/follow option and its maximum wait, and how `cancel` takes ids.
5. **[HUMAN, optional]** MCP prompts are slash commands that only the human can run.
   - Ask the human to type `/` in Claude Code, find **make_short_film**, and run it with idea "15-second test" and length 15.
   - Summarize the call order it suggests in ≤ 5 lines under "Call recipes". Don't run those calls now.
6. Run `wc -w TOOLS.md`. It must be ≤ 1,800 words; trim it if it's longer.

## Outputs
- TOOLS.md filled in.

## Done when
- [ ] Every tool is confirmed or marked not present.
- [ ] The media-link and job-wait notes are filled in.
- [ ] TOOLS.md is ≤ 1,800 words.

## If it fails
- **The tool list is empty:** go back to P1-T02 and check `/mcp`.
- **A tool's purpose is unclear:** read only its description field, then summarize it in one line.

## STATUS line
`P1-T05 DONE · 18 tools documented; media via return_media=link` (example)
