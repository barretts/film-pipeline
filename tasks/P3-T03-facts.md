# P3-T03 · Facts + truth check: `tools/facts.py`

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P3-T01 | none | 60–90 min | — |

**Goal:** enforce the truth rule mechanically. On-screen facts can only come from `edit/facts.json`, and that file is built only from the MCP logs.

## Spec
- **`facts.py build [--out edit/facts.json]`** reads `logs/mcp_calls.jsonl`, plus `logs/mcp_raw/` files when a value isn't in the compact line. Each leaf is stored as `{"value": …, "seq": [evidence seq numbers]}`. It records:
  - `tools`: an object **keyed by tool name**: `tools.<name>` = {`name`, `first_seq`, `count`, `first_ts`}. Also `tools_order`, the list of names in order of first successful use.
  - `server`: `name`, the MCP server name from the `tool_name` prefix. Also `product` and `version` when `studio_status` reports them; the closing title card uses these.
  - `models`: from `load_model` args, each with `id`, `variant`, `kind`, `first_seq`;
  - `media`: counts of images, videos, audio by mode, and transcriptions;
  - `video`: the distinct size/frames/fps combinations requested;
  - `training`: `base_model`, `steps`, `run_id`, `first_loss`, `final_loss`, `min_loss` (when present in tool results), and `loss_curve` (value `train/loss.csv`, evidence = the seqs listed in `train/summary.json`; only once both files exist, in P6-T09);
  - `export`: `format`, `quant`, `size` (when present);
  - **Which run:** when `train/summary.json` exists, `training.*` and `export.*` come **only** from calls that mention its `run_id`, or from the export of that run. Otherwise they come from the most recent finished run. Each fact includes the `run_id` it came from.
  - `totals`: calls, plus the sum of `duration_s` per tool;
  - `features`: when `script/features.json` exists, its entries merged by id (`features.f01.title`, …), with their evidence seqs.
- **`facts.py get <key.path>`** prints one value. For example, `facts.py get features.f03.title` is how the builder reads values.
- **`facts.py check "<text>" [--file lines.txt]`** passes only if every number-like token (`121`, `0.87`, `Q4_K_M`, `4060`) and every tool or model name in the text appears in `facts.json` values or in the logged args and results. It prints the unmatched tokens and exits 1 if there are any.
- **Read-only:** it never writes to `logs/`.

## Steps
1. Write the script.
2. Run `facts.py build` on the current logs from P1 and P2. Check that `facts.json` contains `studio_status`, `generate_image` and `generate_video` with seq numbers.
3. Tests:
   - `check "generate_video"` passes;
   - `check "121 frames"` passes, because P2-T04 asked for 121;
   - `check "loss 0.0001"` fails;
   - `check --file` works on a two-line file;
   - `get tools.generate_video.name` prints `generate_video`;
   - `get tools_order` prints a compact list.
4. Print a short summary of `facts.json` (top-level keys and counts), ≤ 15 lines.

## Outputs
- `tools/facts.py`, `edit/facts.json`.

## Done when
- [ ] Build, get and check all work, including the failing case.
- [ ] `facts.json` shows evidence seqs for every value.

## STATUS line
`P3-T03 DONE · facts.json from 84 calls; check passes/fails correctly` (example)
