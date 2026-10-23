# P6-T09 · Fine-tune + loss curve

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P5-T03 | Qwen3-0.6B (training), then the exported GGUF | 30–60 min | — |

**Goal:** fine-tune Qwen3-0.6B with LoRA and export it to GGUF Q4_K_M, all through MCP. Its **real loss curve** becomes the chalk line in the classroom shot.

**Read first:** TOOLS.md › "Where the training loss history comes from" (from P2-T13).

## Steps
1. **Dataset:** about 200 short chat examples in her voice. Each is a question about the machine or a feature, answered in her quiet, precise style. Use the script and `features.json`, and no personal data.
   - Prefer `run_recipe` (Data Recipes) if it's available, so the dataset build itself is logged.
   - Otherwise, have the writer model produce 4 batches of 50 JSONL lines each, in instruct mode. Check every line parses, then concatenate them into `train/dataset.jsonl`. Don't hand-type 200 examples.

   Then check the format with `datasets`.
2. Call `start_training` with `validate_only` first, then for real:
   - `unsloth/Qwen3-0.6B`, LoRA r 16, alpha 16, lr 2e-4;
   - 150 steps, seq 1024, logging every step.

   Poll at most once per minute.
3. **Loss history:** get it with the method recorded in P2-T13 and write `train/loss.csv` (`step,loss`). Call `list_training_runs` once at the end, so the run id and checkpoints are in the logs.
4. Call `export_model` with format gguf and quant Q4_K_M, then wait with `get_job`. Record the export name and size from the response.
5. Write `train/summary.json`. Copy every value from tool results, and list the seq numbers they came from:
   ```json
   {"run_id": "...", "base_model": "unsloth/Qwen3-0.6B", "steps": 150, "first_loss": 0.0, "final_loss": 0.0, "min_loss": 0.0,
    "duration_s": 0, "export": {"format": "gguf", "quant": "Q4_K_M", "size": "..."}, "loss_source": "...", "evidence_seq": []}
   ```
6. Optional, "the new model speaks":
   - load the GGUF and `chat` one in-character line;
   - if the film uses that line on screen, it counts as a fact and is already logged.

   Unload afterwards.
7. Run `facts.py build`, then confirm that `training.run_id` equals `run_id` in `train/summary.json`. That proves the facts come from this run, not the P2 smoke test. Check that `training.loss_curve` and `export.*` exist. Then run `facts.py get <ref>` for each fact ref that P5-T03 listed as pending; every one must now resolve.

## Outputs
- `train/dataset.jsonl` (or the recipe output), `train/loss.csv`, `train/summary.json`, the GGUF export.

## Done when
- [ ] The loss CSV has ≥ 100 rows.
- [ ] The export completed.
- [ ] Every training and export fact ref resolves.

## STATUS line
`P6-T09 DONE · 150 steps, loss 2.41→0.93, GGUF Q4_K_M 0.4 GB` (example)
