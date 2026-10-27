# Handoff — Local AI short-film pipeline for oh-my-pi

Written 2026-10-26 against `main` at `6fd2f90` (`P1-T03 DONE`). Canonical project root: **F:/film-pipeline** (the `C:/code/local-agent-mode-sessions/outputs` copy is stale). This document replaces the 2026-10-24 handoff, which was written at `8585f5c` and is now superseded.

## Supersessions (the previous handoff was stale — corrected here)

1. **P1-T02 is DONE**, not BLOCKED. OMP MCP connects and authenticates (23 tools), `studio_status` returns, `unsloth doctor --mcp` is OK. The old "block pending host MCP reload" / Codex-connection note no longer applies.
2. **P1-T03 is DONE** and **live-verified**. The "OMP logging compatibility is unverified" concern is resolved: a logging hook is installed and proven to fire on real calls from a standard OMP CLI session (see below). The truth-rule contract it enforces is unchanged.
3. The MCP server id in `mcp.json` is **`unsloth-studio`**, but the tool names the hook sees live are **`mcp__unsloth_studio_<tool>`** — server and tool both underscore-sanitized, joined by a single `_`. This single fact was the root cause of P1-T03's parser bug; it is now handled.

## Start here

Continue the task package in `START_HERE.md`, `CONTEXT.md`, `STATUS.md`, and `tasks/*.md`, using **oh-my-pi (OMP)**. Take the first `STATUS.md` row whose `Needs` are DONE/SKIPPED (currently **P1-T04**). Stop at every ✋ / `[HUMAN]` gate. Record a Result of ≤15 words in `STATUS.md`; full detail to `logs/tasks/<ID>.md`. Commit after each DONE/BLOCKED row.

**ONE task at a time.** No parallel agents, background GPU jobs, or interleaved work. An agent model must not occupy the film's GPU (START_HERE.md agent-runtime constraint).

## Verified OMP MCP setup (re-check before production, not re-derived daily)

- Server `unsloth-studio`, `type: http`, `enabled: true`, endpoint `http://127.0.0.1:8888/mcp/`.
- Config: default-profile `C:/Users/barrett/.omp/agent/mcp.json`. It stores the command that reads the Windows **User**-scope `UNSLOTH_API_KEY` — never the key itself. **Never print the key value.**
- Studio local health: `http://127.0.0.1:8888/api/health` → `{"status":"healthy"}`. `/mcp test unsloth-studio` reports 23 tools. `unsloth doctor --mcp` OK. Server reported `unsloth-studio v2026.10.8`.
- **No `timeout` key is set on the server entry** (verified). OMP's default MCP timeout (~60 s) is shorter than long Studio jobs (image/video generation, training, export can wait 240 s+). Adding `"timeout": 0` to that entry is HELD behind a ✋ because it edits the auth-bearing config file — get explicit approval before changing it, and do it **before the first long P2 job**.

## MCP logging hook — now in place (P1-T03)

The hook is the pipeline's truth source. On-screen facts come from `logs/mcp_calls.jsonl` + `logs/mcp_raw/` — never hand-author or repair them, and never claim pre-hook diagnostics were captured by it.

- **Only standard OMP CLI is hookable.** An agent-mode harness (this `local-agent-mode-sessions` client) exposes Studio MCP as `write`→`xd://mcp__unsloth_studio_<tool>` host-bridge devices, which do **not** emit `tool_call`/`tool_result` (see `omp://docs/hooks.md`) and therefore fire no hooks. Standard OMP CLI registers each MCP tool as an AgentTool and fires `tool_call`/`tool_result` on every call. **Run MCP-dependent / hook-verifying work in a standard `omp` session launched from `F:\film-pipeline`** (the hook is discovered from `<cwd>/.omp/hooks/post/` — wrong cwd = no hook = empty log).
- **Hook:** `.omp/hooks/post/unsloth-log.ts` (committed shape from `cd4f56a`). Passive `pre`/`post`/`fail` handlers filter `toolName.startsWith("mcp__unsloth")` and pipe UTF-8 JSON to `tools/log_mcp.py`. Correlation uses a per-tool FIFO id (`<toolName>#N`) rather than `toolCallId`, because `toolCallId` is not guaranteed on `tool_call`. `duration_s` comes from the `pre` timestamp paired with the matching `post`/`fail`.
- **Redactor:** `tools/log_mcp.py` (stdlib only). Reads stdin as UTF-8 bytes (Windows safety). Redacts credential-shaped keys (`SECRET_KEY_RE`, plus `*_token`/`*_secret`/`*_api_key`) and `sk-unsloth-*`; drops base64 blobs; truncates. Writes the compact line to `logs/mcp_calls.jsonl` (append-locked) and the full payload to `logs/mcp_raw/<seq>_<tool>.json`. `split_server_tool()` maps the live name `mcp__unsloth_studio_<tool>` → `server="unsloth-studio"` + short `tool` (handles the hyphen `unsloth-studio__<tool>` form too; multi-underscore tools like `list_training_runs` keep their full name).
- **Evidence:** offline regression `logs/tasks/p1t03_hooktest.ts` (throwaway temp log via `FILM_LOG_DIR`) fires the real tool names → **14/14 green** (args captured from `tool_result.input`, `api_key`→`<redacted>`, no raw secret, UTF-8 `café × “q”`, ok true/false, numeric `duration_s`, bash ignored). A live standard-OMP-CLI run fired both calls and logged them (success + failure, correct `duration_s`, raw archived, no keys, no `hook_errors.log`). **If a future session changes the hook or `log_mcp.py`, re-run that regression and, for a hook change, one live `studio_status` call.**

## Where the task package stands

| Row | Status | Note |
|---|---|---|
| P0-T01…T04 | DONE | Hardware, prereqs, Windows settings + model drive (HF_HOME=`F:\hf`), venv + git scaffold |
| P1-T01 | DONE | Studio installed + HTTP 200; idle auto-unload 60 s; residency controls off |
| P1-T02 | DONE | MCP connected (23 tools), `studio_status` OK, doctor OK, server `unsloth-studio` v2026.10.8 |
| P1-T03 | DONE | Logging hook live-verified; `log_mcp.py` server/tool parser fixed |
| P1-T07 | DONE | HyperFrames render recipe; starter MP4 ffprobe-verified; `RENDER_CMD` in `TOOLS.md` |
| P1-T08 | DONE | `tools/contact_sheet.py` (images + video frames, ≤1600 px, ≤16 tiles) |
| P1-T04 → T06 | TODO | Next sequential work (all trace back to P1-T03, now unblocked) |

Prior DONE rows were not re-measured in this update; trust their task logs before reusing a number.

## Next task: P1-T04 (VRAM sampler + MCP report) — `tasks/P1-T04-vram-sampler-report.md`

Two **stdlib-only Python** scripts, no GPU model load:
- `tools/vram_sampler.py` — poll `nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu` every `--interval` s (default 1.0), append `epoch_s,used_mib,total_mib,util_pct` to `logs/vram.csv` (header when new, flush each line, rotate at 50 MB, survive `nvidia-smi` errors with an empty row, clean Ctrl+C). Options `--interval --out --once --nvsmi`.
- `tools/mcp_report.py` — join `logs/mcp_calls.jsonl` with `logs/vram*.csv`; peak VRAM per call = max `used_mib` in `[t_start − interval, t_end + interval]` (use `t_end − 1 − interval` when `t_start` is null); widen job windows (`generate_video`, `start_training`, `export_model`, `run_recipe`) to the last call sharing the job/queue id; `--last --since --tool --job --seq-only --json-out`; emit a ≤40-row Markdown table (`seq|tool|key args|ok|dur s|peak VRAM GB|window s`) + ≤3 summary lines, never raw results.
- **Synthetic test** with known numbers (a 0.3 s call, a job id spanning 3 calls) asserting peaks, the job window, that a sub-second call still gets a peak, and `--seq-only` output. Record it in `logs/tasks/P1-T04.md`. Every later task takes its numbers and `mcp_seq` from `mcp_report.py`, never by reading the raw log.

After P1-T04: **P1-T05** fill `TOOLS.md` (Needs P1-T03), **P1-T06** `MODELS.md` + large model downloads ~150–250 GB (Needs P1-T05; heavy disk, ✋ around licensing/downloads), then **P2** model smoke tests (✋ **P2-T15** stack review), **P3** CPU tooling (build only after real P2 assets exist), **P4** pilot ✋, **P5** pre-prod ✋, **P6** production, **P7** post ✋.

## GPU contention — resolve before the first P2 model load

`studio_status` hardware last showed ≈ **15.2–15.3 / 16.0 GB VRAM already used outside Studio** (external process contention on the 4060 Ti). One model at a time is the rule, but with only ~1 GB free nothing loads. **Free the GPU (close the competing process / release VRAM) and re-check `studio_status` before any P2 load.** P1-T04 needs no model and is unaffected.

## Operating constraints (still in force)

- Read `CONTEXT.md` for the full rules. One GPU model in VRAM at a time; inspect `studio_status` before every load. Any documented audio exception must meet its stated free-memory condition.
- Local generation goes through Studio MCP only. Preserve model/lane decisions; ask at every ✋ checkpoint; do not infer an undecided choice.
- Never print, paste, or store the API key in files, chat, or logs. `mcp.json` stores only the command that reads the User-env value.
- Use absolute forward-slash Windows paths in Studio arguments (`F:/film-pipeline/...`); keep manifest-internal paths relative as specified.
- **Context budget (§9):** never `cat`/`tail`/`grep` `logs/mcp_calls.jsonl` or `logs/mcp_raw/` except the single allowed `tail -n 1`. Use `tools/mcp_report.py` (once P1-T04 lands) for call summaries. Review images only as contact sheets ≤16 tiles via `tools/contact_sheet.py`. Keep noisy output in task-specific files.
- Shell note: the project Python convention is `.venv/Scripts/python.exe`. In the agent-mode harness shell (MSYS bash), the venv/system `py` are not exec-able directly — run Python via `powershell -NoProfile -Command "py -3 ..."` or the venv exe by full path. The hook runs `py -3` and Studio tools resolve paths on the Studio host (this machine).

## What could not be verified here (re-check, do not assume)

- The live two-line P1-T03 evidence was produced in a **separate standard-OMP-CLI session**, not this harness (which cannot fire the hook). Its truth-log lines remain in `logs/`; re-verify the fixed parser with one live `studio_status` if you want fresh confirmation (expect `server:"unsloth-studio"`, `tool:"studio_status"`), but do not hand-edit the log.
- Current VRAM, loaded/resident models, active jobs, Studio residency settings, and `doctor` status were not re-sampled this update; re-establish them at the start of the next Studio-dependent task.
- Historical hardware, render, model, and license claims from P0/P1-T01/T07/T08 were not re-run; their evidence is in the task logs.

Confirmed for this update: canonical root/branch/tip (`6fd2f90`), default-profile `mcp.json` has no literal key and no `timeout` key, P1-T02/P1-T03 completion records match their task logs, and `log_mcp.py` parses every observed tool-name form (verified directly + 14/14 offline regression).
