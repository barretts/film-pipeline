# P5-T05 · ✋ Stills for every shot

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT → HUMAN approves | P5-T04 | Qwen-Image-2.1-Turbo (reference mode) | 1–2 h | ✋ yes |

**Goal:** one approved, on-model 1344×768 still per shot. Each still is the start frame for that shot's video.

## Steps
1. Create `jobs/stills.json` with `tools/manifest.py`: one item per shot × 2 takes (`<shot>_still_t1`, `_t2`). Params:
   - `prompt`: the shot's `still_prompt` + the style suffix from P5-T04;
   - `reference`: `[<ROOT>/stills/character_master.png]`, plus `<ROOT>/stills/character_sheet.png` if it exists. Use absolute paths. For shots where `has_character` is false, use txt2img with no reference.
   - `size`: 1344×768;
   - `seed`: the shot's seed for t1, seed + 1 for t2.
2. Load the image model. Loop, **≤ 8 items per session**:
   1. `manifest.py next`
   2. `generate_image` (as a link)
   3. download to `stills/candidates/<id>.png`
   4. `manifest.py set … status=done outputs+=… mcp_seq+=…`, taking the seq from `mcp_report.py --last 1 --seq-only`
3. For every 8 shots, make a contact sheet with t1 and t2 side by side (16 tiles), and view it.
   - Pick one take per shot and copy it to `stills/<shot>_still.png`, then mark it `picked`.
   - If you can't view images, ask the human to pick from the sheet.
4. Reject rule: if she is off-model (face, hair, coat or palette), or there are artifacts, regenerate with a new seed (max 3 attempts per shot), then simplify the prompt.
5. **[HUMAN] ✋** Show the final picks, ≤ 16 per sheet, and ask "Approve these stills? (yes / redo s07, s12 …)". Redo as asked.
6. Unload.

## Outputs
- `stills/<shot>_still.png` for every shot; `jobs/stills.json` with every item done or picked.

## Done when
- [ ] Every shot has an approved still.
- [ ] `manifest.py summary jobs/stills.json` shows no `todo`.
- [ ] The human approved.

## STATUS line
`P5-T05 DONE · 20/20 stills approved; 6 regenerations` (example)
