# Handoff — Local AI short-film pipeline

**Generated:** 2026-10-23. Canonical root: **`F:/film-pipeline`** (the `C:/code/local-agent-mode-sessions/outputs/...` copy is STALE — ignore it). Objective: execute the plan in `local-ai-film-plan.md` as the task package in `START_HERE.md` + `STATUS.md` + `tasks/*.md`.

## HARD RULE (owner, highest priority)
**ONE task at a time, forever.** No parallel subagents, no parallel/background GPU jobs, no interleaved edits. Pick one next task, finish or park it, then move on. This supersedes any workflow that suggests fan-out.

## Where we are (evidence-backed)
- **DONE & committed** — latest verified tip before the current Studio-resume updates: `a9ba83a`; seven commits from scaffold through P1-T08 and handoff (`707a614`, `f3978ab`, `1855823`, `1bf2832`, `75e8318`, `5a25405`, `a9ba83a`).
  - **Phase 0 (P0-T01..T04) complete.** RTX 4060 Ti 16 GB (driver 591.86, CUDA 13.1, PCIe Gen3 x8), 128 GB DDR4, model drive **F:** NVMe. `HF_HOME=F:\hf`, Dev Mode on, no-AC-sleep. venv on **Python 3.13**; requirements installed via PowerShell; imports OK.
  - **P1-T07 HyperFrames DONE** — v0.8.188 via `npx --yes hyperframes …`; starter render verified `render/renders/starter.mp4` (1920×1080, 24 fps, 240 f, 10.000 s). `RENDER_CMD` recorded in `TOOLS.md` (lines ~47–60). Skills at `C:\Users\barrett\.claude\skills\hyperframes*`.
  - **P1-T08 contact-sheet tool DONE** — `tools/contact_sheet.py` (231 lines): `--images/--videos`, ≤16 tiles (17 → exit 2, writes nothing), sheet ≤1600 px, JPEG q80; tested (images+video→5 tiles; over-limit→exit 2).
- **P1-T01 DONE; P1-T02 BLOCKED.** Studio `127.0.0.1:8888` returns HTTP 200; `/openapi.json` reports **2026.10.8**. Resources settings were confirmed conservative, with image/video auto-unload saved at **60 seconds**. `/api/health` identifies the Unsloth UI Backend; Codex config contains `[mcp_servers.unsloth-studio]`; `unsloth doctor --mcp` returns Verdict OK with process-only `UNSLOTH_STUDIO_URL=http://127.0.0.1:8888`. The agent runs as isolated `CodexSandboxOffline`, so host User-scope key state is not inspectable here; no host write is claimed. The current Codex tool inventory has no Unsloth tools. Resume when the key is stored in the user's Windows PowerShell and Codex MCP is restarted; then call `studio_status`. See `logs/tasks/P1-T02.md`.
- **Everything else is gated behind P1-T01.** `P1-T02 → … → P2 → P3 → P7` all need a running Studio/MCP. The CPU-only P3 tooling is *deliberately* built only after real Phase-2 assets exist — do **not** pre-build it (violates the task's declared Needs).

## Why :8888
`http://127.0.0.1:8888/` is Studio's UI; `…/mcp/` (Bearer `${UNSLOTH_API_KEY}`) is the MCP endpoint. It answers only after `unsloth studio` runs. `000` = not started; `200`/`30x` = up.

## Environment / conventions a fresh context MUST obey
- Agent shell = **Git Bash**; `USERPROFILE=C:\Users\barrett`. MSYS can't exec the venv `python.exe` stub → run venv `python`/`pip` via **PowerShell**: `& 'F:\film-pipeline\.venv\Scripts\python.exe' …`. In PowerShell 5.1: NO `&&`/`||`, `/dev/null`, `head`; single-quote `$env:` from bash.
- Always address the project by absolute **`F:/…`** (or MSYS `/f/film-pipeline/…`). Bash log redirects MUST be absolute: `LOG=/f/film-pipeline/logs/tasks/<ID>.out`.
- §3 golden rules: one GPU model in VRAM at a time; local models via Studio MCP only; **on-screen facts MUST come from `logs/mcp_calls.jsonl`** (truth rule); API key only in user env `UNSLOTH_API_KEY` — **never print the key/env value**.
- §3.7 **ask the human before**: admin rights, installers (`winget`/community binaries), license clicks, community custom nodes, deleting non-temporary files.
- §9 context budget: never cat/tail/grep `logs/mcp_calls.jsonl` or `logs/mcp_raw/`; view images only as contact sheets ≤16 tiles.
- MCP registration uses **`unsloth mcp add codex`** for this Codex client (or `unsloth mcp add claude-code` for Claude Code); verified with installed CLI help and Codex dry-run. `unsloth start claude` launches Claude Code against a served model; it is not MCP registration. Protocol: log detail in `logs/tasks/<ID>.md`; STATUS Result cells ≤15 words; ✋/`[HUMAN]` = stop & ask; commit `git add -A && git commit -m "<ID>: …"` after each DONE/BLOCKED row.
- Media standards (§5): film 1920×1080/24 fps H.264 yuv420p + AAC 48 kHz; stills 1344×768 PNG; mix −14 LUFS / ≤−1.5 dBTP. Renders are **silent** at 24 fps (final audio muxed later by `tools/mux_final.py`, P3-T06).
- **Lane PERSONAL vs WORK is a human ✋ decision — NOT yet made.** Only needed at P4/P5 kickoff. Don't pick it.
- `STATUS.md` is at P1-T02. `TOOLS.md` records the verified Studio URL/version; Codex MCP connection and `studio_status` remain to be verified, then P1-T05 will document the tools.

## NEXT STEPS

### A) HUMAN runs these (finish P1-T02)
1. P1-T02 is in progress. In the user's own Windows PowerShell (outside this agent sandbox), run the hidden prompt in `tasks/P1-T02-connect-mcp.md` to store `UNSLOTH_API_KEY` at User scope. The `unsloth-studio` Codex config entry already exists.
2. Restart Codex so the configured MCP server and User environment are loaded. Then say **"continue"**; the active tool inventory currently lacks Unsloth MCP tools.
3. **If Studio stops answering**, check it with:
   ```
   curl -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8888/
   ```
   Expect `200`/`30x`.

### B) AGENT resumes after the human setup gate is complete
1. **P1-T02:** confirm the User-scope key is available, reload Codex's configured MCP runtime, verify the server tools appear, then call `studio_status` once. Fill the TOOLS.md MCP header, log `logs/tasks/P1-T02.md`, update `STATUS.md`, and commit.
3. **P1-T03:** MCP logging hook — human reviews `templates/claude-settings.json` + `tools/log_mcp.py` before install (§3.7 consent). **P1-T04:** VRAM sampler + `tools/mcp_report.py`. **P1-T05:** fill `TOOLS.md` MCP table. **P1-T06:** `MODELS.md` + start the big model downloads.
4. **P2-T01..T14:** 15 model smoke tests (write VRAM+time to `logs/`), then ✋ **P2-T15** stack review (human). **P3** CPU tooling against real assets. **P4** pilot + ✋. **P5** pre-prod (✋ lane/script/character/stills). **P6** production (evening hero-shot queue). **P7** post (captions, EDL, mix −14 LUFS, HyperFrames render + mux, ✋ review).
- **Stop at every ✋ and `[HUMAN]` gate. Commit after each DONE/BLOCKED row. One task at a time.**
