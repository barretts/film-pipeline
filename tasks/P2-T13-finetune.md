# P2-T13 · Fine-tune: Qwen3-0.6B LoRA → GGUF

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T04, P1-T06 | Qwen3-0.6B (training) | 30–60 min | — |

**Goal:** prove the full training loop works over MCP (dataset → train → export GGUF), and find out where the **loss history** comes from. It becomes the chalk line in the film.

## Steps
1. Write `tests/fixtures/ft_tiny.jsonl`: 40 short chat examples in the character's quiet voice, about what the machine does. Use the format from TOOLS.md `datasets` (e.g. `{"messages":[{"role":"user","content":"…"},{"role":"assistant","content":"…"}]}`). Use no personal data.
2. Check the format with `datasets` (check_format), then register or upload the file the way TOOLS.md says. A local path may work.
3. Call `start_training` with **validate_only = true** and fix the config until it's valid:
   - base `unsloth/Qwen3-0.6B`
   - LoRA r 16, alpha 16, lr 2e-4
   - max_steps 60, seq 1024, batch 2, grad_accum 4
   - log every step
4. Run `start_training` for real. Poll at most once per minute until it finishes. Record minutes and peak VRAM.
5. **Loss history.** Check these sources in order and use the first that works:
   - (a) fields in `list_training_runs`, `get_job` or `studio_status`;
   - (b) the run's `trainer_state.json` (`log_history`) on disk under Studio's data folder.

   Save `step,loss` rows to `tests/fixtures/loss_test.csv`. Record the source in TOOLS.md › Capabilities. Prefer (a): those values then sit in the MCP logs.
6. Call `export_model` with format gguf and quant Q4_K_M. Wait with `get_job`, then record the export name and size from the response.
7. Optional: load the exported GGUF, `chat` one line to confirm it runs, then unload.

## Outputs
- `tests/fixtures/ft_tiny.jsonl`, `loss_test.csv`
- Export details in the task log; loss source in TOOLS.md

## Done when
- [ ] Training completed.
- [ ] The loss CSV has ≥ 20 rows.
- [ ] The GGUF Q4_K_M export completed.
- [ ] The loss source is recorded.

## If it fails
- **Validation errors:** follow the error text. Common causes are column names and the chat template. The human can run the MCP prompt **build_dataset_and_train** from the `/` menu to show the expected call order; only the human can run slash commands.
- **The loss only comes from (b):** in P6-T09, also call `list_training_runs` after training so the run id is in the logs, and cite the file path plus seq in `train/summary.json`.

## STATUS line
`P2-T13 DONE · 60 steps in 4 min; loss via list_training_runs; GGUF 0.4 GB` (example)
