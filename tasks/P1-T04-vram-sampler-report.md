# P1-T04 · VRAM sampler + MCP report

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 2 scripts) | P1-T03 | none | 45–90 min | — |

**Goal:** sample VRAM continuously, and give a compact per-call report of duration and peak VRAM. Every later task takes its measurements and `mcp_seq` numbers from this report, never by reading the log directly.

## Spec: `tools/vram_sampler.py`
- **Sampling:** every `--interval` seconds (default 1.0), run:
  ```
  nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits
  ```
  Append `epoch_s,used_mib,total_mib,util_pct` to `logs/vram.csv`. Write a header when the file is new, and flush every line.
- **Options:** `--interval`, `--out`, `--once` (print one sample and exit), `--nvsmi PATH`.
- **Rotation:** at 50 MB, rename the file to `logs/vram.<n>.csv`.
- **Robustness:** survive nvidia-smi errors by writing a row with empty values and continuing. Exit cleanly on Ctrl+C. Standard library only.

## Spec: `tools/mcp_report.py`
- **Inputs:** `logs/mcp_calls.jsonl` and `logs/vram*.csv`.
- **Peak per call:** the highest `used_mib` in the window [`t_start` − interval, `t_end` + interval]. Widening by one sampling interval means sub-second calls still get a sample. If `t_start` is null, use `t_end` − 1 − interval.
- **Job windows:** for calls that start async work (`generate_video`, `start_training`, `export_model`, `run_recipe`), the window runs from that call's `t_start` to the `t_end` of the last call whose `ids` or `args` mention the same job or queue id.
- **Options:**
  - `--last N` (default 15), `--since ISO`, `--tool NAME`, `--job ID`;
  - `--seq-only`: one line per call, `seq tool ok`, and nothing else. Use it to fill `mcp_seq` in manifests.
  - `--json-out PATH`.
- **Output:**
  - a Markdown table of ≤ 40 rows: `seq | tool | key args (≤ 50 chars) | ok | dur s | peak VRAM GB | window s`;
  - then ≤ 3 summary lines: number of calls, total time, max VRAM.
  - It never prints raw results.

## Steps
1. Write both scripts to the spec.
2. Test the sampler:
   ```bash
   .venv/Scripts/python tools/vram_sampler.py --once
   ```
   It should print one sample.
3. **Synthetic test.** Build a temp `jsonl` and `vram.csv` with known numbers, including a 0.3 s call and a job id that spans 3 calls. Assert:
   - the peaks are correct;
   - the job window is correct;
   - the 0.3 s call still gets a peak;
   - the `--seq-only` output is right.

   Record the test in the task log.
4. **[HUMAN]** Start the sampler in its own terminal, in the project folder, and **leave it running through P2–P7**:
   ```powershell
   .venv\Scripts\python.exe tools\vram_sampler.py
   ```
5. Make two MCP calls: `studio_status` and `list_models(source="local")`. Use the **local** source, never the unfiltered catalog. Then run:
   ```bash
   .venv/Scripts/python tools/mcp_report.py --last 5
   .venv/Scripts/python tools/mcp_report.py --last 2 --seq-only
   ```

## Outputs
- `tools/vram_sampler.py`, `tools/mcp_report.py`
- `logs/vram.csv` (growing)

## Done when
- [ ] The synthetic test passes.
- [ ] The live report shows both calls with a peak VRAM value.
- [ ] `--seq-only` prints 2 lines.
- [ ] The sampler is running in its own window.

## If it fails
- **nvidia-smi isn't on PATH:** pass `--nvsmi "C:/Windows/System32/nvidia-smi.exe"`.
- **Peaks are empty:** check the clocks. Both files use epoch seconds from the same PC.

## STATUS line
`P1-T04 DONE · sampler running; report + seq-only work` (example)
