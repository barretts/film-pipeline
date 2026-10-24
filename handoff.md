# Handoff — Local AI short-film pipeline for oh-my-pi

Written 2026-10-24 against `main` at `8585f5c` (`P1-T02: block pending host MCP reload`). The working tree was clean before this documentation update. Canonical project root: **F:/film-pipeline**. The older C:/code/local-agent-mode-sessions/outputs copy is stale.

This update verifies OMP configuration and MCP connectivity only. Earlier production, hardware, model, and render results remain recorded in the task logs; they were not rerun here. This handoff change is uncommitted.

## Start here

Continue the local AI short-film task package in `START_HERE.md`, `CONTEXT.md`, `STATUS.md`, and `tasks/*.md`, using **oh-my-pi (OMP)**. The user explicitly requested OMP and its Unsloth MCP setup. The setup is now verified; do not repeat API-key creation or wait for Codex to connect.

**ONE task at a time.** No parallel agents, background GPU jobs, or interleaved work. Preserve every human checkpoint and task dependency. An agent model must not occupy the film's GPU; follow START_HERE.md's agent-runtime constraint.

### The three things to do first

1. Read `CLAUDE.md`, `START_HERE.md`, `CONTEXT.md`, `STATUS.md`, this handoff, and `logs/tasks/P1-T02.md`. The Codex-specific resume instructions and missing-key claims in those older task records are superseded by the verified OMP setup below. Record the client change when resuming P1-T02; do not pretend the original Codex connection criterion passed.
2. Start OMP in the canonical project, then reload/test MCP in that session:
   ```powershell
   Set-Location 'F:\film-pipeline'
   omp
   ```
   In OMP, run `/mcp reload`, then `/mcp test unsloth-studio`. Leave Studio running. A named OMP profile has separate user configuration; this setup is for the default profile.
3. Resume **P1-T02**: call the discovered `studio_status` tool once, summarize server name and free GPU memory in `TOOLS.md` and the task log, and rerun the task's `unsloth doctor --mcp` check. Inspect installed help before assuming doctor supports OMP registration. Update the task wording/result to the user-authorized OMP client, then update STATUS and commit only after the applicable completion criteria pass. If doctor cannot validate OMP, record the precise limitation and the native OMP connection evidence; do not invent a passing doctor result.

## Verified OMP MCP setup

Checked 2026-10-24, including a fresh test from **F:/film-pipeline**:

- Installed client: `omp/18.12.6`.
- Default-profile user config: `C:/Users/barrett/.omp/agent/mcp.json`.
- Server: `unsloth-studio`, `type: http`, `enabled: true`.
- Endpoint: `http://127.0.0.1:8888/mcp/`.
- The Windows User environment contains `UNSLOTH_API_KEY`; only presence/format/equality were checked, never its value printed.
- Authorization uses OMP's command-based header resolution. The config contains this command, not the credential:
  ```json
  "Authorization": "!powershell.exe -NoProfile -NonInteractive -Command \"'Bearer ' + [Environment]::GetEnvironmentVariable('UNSLOTH_API_KEY','User')\""
  ```
- OMP's own `/mcp test unsloth-studio` returned:
  ```text
  Server "unsloth-studio" connected (23 tools).
  ```
  The RPC diagnostic exited 0 and reported `agentInvoked: false`; it did not invoke an AI model or generate media.
- Advertised tools: `studio_status`, `list_models`, `load_model`, `unload_model`, `plan_load`, `download_model`, `chat`, `embed`, `system_one`, `generate_image`, `generate_audio`, `transcribe`, `analyze_audio`, `generate_video`, `run_recipe`, `get_job`, `datasets`, `start_training`, `list_training_runs`, `export_model`, `list_media`, `voices`, `cancel`.

Tool discovery proves connection and authentication, not successful execution of every tool. Inspect OMP's actual mounted tool names and schemas; do not assume Codex/Claude naming conventions.

### Repeat the connection check without a model turn

Run in Windows PowerShell from the project folder:

```powershell
'{"id":"unsloth-check","type":"prompt","message":"/mcp test unsloth-studio"}' |
  omp --mode rpc --no-ui --no-session --allow-home --no-extensions --no-skills --no-rules |
  ForEach-Object {
    try {
      $frame = $_ | ConvertFrom-Json
      if ($frame.type -in @('response', 'command_output', 'prompt_result', 'notice')) {
        $frame | ConvertTo-Json -Depth 12 -Compress
      }
    } catch {}
  }
```

The discovery-only flags above belong to this diagnostic, not the normal OMP launch. Expected output is the connection message plus a successful response with `agentInvoked: false`.

## Where the task package stands

As read at `8585f5c`, STATUS.md records P0, P1-T01, P1-T07, and P1-T08 as DONE. P1-T02 is BLOCKED with an outdated Codex connection reason; subsequent Studio-dependent tasks are TODO. Those earlier DONE results were not reverified in this update; use their task logs before relying on measurements.

**P1-T02 is not yet claimed DONE:** OMP connection/tool discovery is verified, but this update did not call `studio_status`, fill the TOOLS header, rerun doctor, or change the task/status records.

After P1-T02, continue sequentially through P1-T03 logging, P1-T04 VRAM sampler/report, P1-T05 tool reference, and P1-T06 model mapping. Follow the task dependencies for smoke tests, stack review, CPU tooling, pilot, production, and post. Do not pre-build P3 tooling before its real-asset prerequisites exist.

## OMP logging compatibility is the next setup concern

P1-T03 was written for a Claude Code hook (`templates/claude-settings.json` and `tools/log_mcp.py`). OMP connectivity does **not** prove that this hook runs in OMP. Inspect P1-T03 and OMP's supported extension/hook interface, adapt the logging path with the required human review, and verify that MCP calls actually produce the required records before model/media work.

Keep the truth-rule contract: on-screen facts come from `logs/mcp_calls.jsonl` / `logs/mcp_raw/`; do not hand-author or repair those evidence logs. Do not claim pre-logging diagnostics were captured by the production hook. If changing the client requires adapting other Claude-specific tasks, make the adaptation explicit and preserve each task's outputs and human gates.

## Operating constraints

- Read CONTEXT.md for the complete rules. One GPU model at a time; inspect `studio_status` before loads. Any documented audio exception must satisfy its stated free-memory condition.
- Local generation goes through Studio MCP. Preserve model/lane decisions and ask at every marked human checkpoint; do not infer an undecided choice from the earlier handoff.
- Never print, paste, or store the API key in files, chat, or logs. The OMP config only stores the command that reads the existing User environment value.
- Use absolute Windows paths with forward slashes in Studio arguments, e.g. `F:/film-pipeline/stills/...`; preserve relative paths inside manifests as specified.
- Windows PowerShell is the verified shell for this update. Use PowerShell syntax; do not assume an OMP tool named `bash` executes Git Bash. Run project Python with `& 'F:\film-pipeline\.venv\Scripts\python.exe'` when needed.
- Keep noisy output in task-specific files. Never dump/search raw MCP logs; use `tools/mcp_report.py` when available. Review images through contact sheets within the task's tile limit.
- Preserve the specified film media standards in CONTEXT.md and existing HyperFrames launch recipe in TOOLS.md. No renders, model downloads, GPU loads, installations, hooks, or production changes were performed in this handoff update.

## What I could not verify

- The receiving interactive OMP session has not been observed; reload and retest there. Only a fresh default-profile OMP RPC process was tested.
- `studio_status` data, free VRAM, active model/job state, Studio residency settings, and doctor status were not checked in this update. Reestablish them before production.
- OMP logging-hook compatibility is unverified. Its cheapest proof is an approved hook plus an actual harmless MCP call that produces the required log record.
- Historical hardware, render, model, license, and task-completion claims were not rerun. Their recorded evidence remains in the project files; this update does not certify them.

## Corrections to the previous handoff

1. The previous handoff told the human to persist the key and restart Codex. User-scope key presence and an authenticated OMP connection are now verified. Resume in OMP instead.
2. A Codex host check returned `enabled: false` with disabled reason `requirements (enterprise-managed requirements Pilot (e11244ca-d99e-4ef2-931a-f8602fec6ab6))`. This was observed earlier in this session, not rerun for this document. Do not treat the Codex restriction as a Studio outage or assume an OMP change enables Codex.
3. An earlier Windows listener check incorrectly suggested no server was running. Authenticated HTTP/MCP responses and OMP's successful connection refute that conclusion. Use a real MCP test for this endpoint.
4. An initial OMP header using `Bearer ${UNSLOTH_API_KEY}` returned 401 in OMP's native test. The command-based header above passed the same test. The interpolation failure's internal mechanism was not established; retain the verified working form.
5. OMP tool discovery does not complete P1-T02 or P1-T03. The required status call, task-record updates, and logging verification remain the receiving agent's work.

Checked and confirmed for this update: canonical repository/branch/tip, clean pre-edit tree, default-profile OMP config without a literal key, installed OMP version, and successful 23-tool discovery from the film-pipeline folder.
