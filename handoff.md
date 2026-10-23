# Handoff — Local AI short-film pipeline

**Generated:** 2026-10-23. Canonical root: **`F:/film-pipeline`** (the `C:/code/local-agent-mode-sessions/outputs/...` copy is STALE — ignore it). Objective: execute the plan in `local-ai-film-plan.md` as the task package in `START_HERE.md` + `STATUS.md` + `tasks/*.md`.

## HARD RULE (owner, highest priority)
**ONE task at a time, forever.** No parallel subagents, no parallel/background GPU jobs, no interleaved edits. Pick one next task, finish or park it, then move on. This supersedes any workflow that suggests fan-out.

## Where we are (evidence-backed)
- **DONE & committed** — latest verified tip before this handoff refresh: `75e8318`; five commits from scaffold through P1-T08 and handoff (`707a614`, `f3978ab`, `1855823`, `1bf2832`, `75e8318`).
  - **Phase 0 (P0-T01..T04) complete.** RTX 4060 Ti 16 GB (driver 591.86, CUDA 13.1, PCIe Gen3 x8), 128 GB DDR4, model drive **F:** NVMe. `HF_HOME=F:\hf`, Dev Mode on, no-AC-sleep. venv on **Python 3.13**; requirements installed via PowerShell; imports OK.
  - **P1-T07 HyperFrames DONE** — v0.8.188 via `npx --yes hyperframes …`; starter render verified `render/renders/starter.mp4` (1920×1080, 24 fps, 240 f, 10.000 s). `RENDER_CMD` recorded in `TOOLS.md` (lines ~47–60). Skills at `C:\Users\barrett\.claude\skills\hyperframes*`.
  - **P1-T08 contact-sheet tool DONE** — `tools/contact_sheet.py` (231 lines): `--images/--videos`, ≤16 tiles (17 → exit 2, writes nothing), sheet ≤1600 px, JPEG q80; tested (images+video→5 tiles; over-limit→exit 2).
- **WAITING ON HUMAN — P1-T01.** On 2026-10-23, `nvidia-smi` showed **994/16,380 MiB used (~6%)** after the local model was shut down. Studio still refuses connections at `127.0.0.1:8888`; `unsloth` is installed at **2026.8.18**; `UNSLOTH_API_KEY` is unset. VRAM pressure is cleared; remaining P1-T01 steps (start Studio, owner account, conservative Resources settings) are human UI steps.
- **Everything else is gated behind P1-T01.** `P1-T02 → … → P2 → P3 → P7` all need a running Studio/MCP. The CPU-only P3 tooling is *deliberately* built only after real Phase-2 assets exist — do **not** pre-build it (violates the task's declared Needs).

## Why :8888
`http://127.0.0.1:8888/` is Studio's UI; `…/mcp/` (Bearer `${UNSLOTH_API_KEY}`) is the MCP endpoint. It answers only after `unsloth studio` runs. `000` = not started; `200`/`30x` = up.

## Environment / conventions a fresh context MUST obey
- Agent shell = **Git Bash**; `USERPROFILE=C:\Users\barrett`. MSYS can't exec the venv `python.exe` stub → run venv `python`/`pip` via **PowerShell**: `& 'F:\film-pipeline\.venv\Scripts\python.exe' …`. In PowerShell 5.1: NO `&&`/`||`, `/dev/null`, `head`; single-quote `$env:` from bash.
- Always address the project by absolute **`F:/…`** (or MSYS `/f/film-pipeline/…`). Bash log redirects MUST be absolute: `LOG=/f/film-pipeline/logs/tasks/<ID>.out`.
- §3 golden rules: one GPU model in VRAM at a time; local models via Studio MCP only; **on-screen facts MUST come from `logs/mcp_calls.jsonl`** (truth rule); API key only in user env `UNSLOTH_API_KEY` — **never print the key/env value**.
- §3.7 **ask the human before**: admin rights, installers (`winget`/community binaries), license clicks, community custom nodes, deleting non-temporary files.
- §9 context budget: never cat/tail/grep `logs/mcp_calls.jsonl` or `logs/mcp_raw/`; view images only as contact sheets ≤16 tiles.
- MCP registration command is **`unsloth start claude`** (not `unsloth mcp add`). Protocol: log detail in `logs/tasks/<ID>.md`; STATUS Result cells ≤15 words; ✋/`[HUMAN]` = stop & ask; commit `git add -A && git commit -m "<ID>: …"` after each DONE/BLOCKED row.
- Media standards (§5): film 1920×1080/24 fps H.264 yuv420p + AAC 48 kHz; stills 1344×768 PNG; mix −14 LUFS / ≤−1.5 dBTP. Renders are **silent** at 24 fps (final audio muxed later by `tools/mux_final.py`, P3-T06).
- **Lane PERSONAL vs WORK is a human ✋ decision — NOT yet made.** Only needed at P4/P5 kickoff. Don't pick it.
- `STATUS.md` pointer line 3 ≈ `P1-T02 (gated on P1-T01 …)`. `TOOLS.md` header lines 5–6 still `_fill in_` (server name, Studio URL/version, `unsloth doctor --mcp` verdict) → fill during P1-T01/T02/T05.

## NEXT STEPS

### A) HUMAN runs these (to clear P1-T01 → P1-T02)
1. **Start Studio:** `unsloth studio` → browser opens `http://127.0.0.1:8888` → **create the owner account** (your credential). **Settings → Resources**: Model memory = most conservative; **"Keep multiple models loaded" = Off** (16 GB card). Current VRAM use is low; no further app-closing step is indicated.
2. **Confirm it's up** (paste output to the agent, or just reply "Studio ready"):
   ```
   curl -s -o NUL -w "%{http_code}\n" http://127.0.0.1:8888/
   ```
   Expect `200`/`30x`.
3. **Mint the API key:** Studio → Settings → API → create a key with **MCP access ON**, then set the user env var (paste your real key; never share it with the agent):
   ```
   setx UNSLOTH_API_KEY "PASTE_KEY_HERE"
   ```
   Then **open a new terminal** so it takes effect.

### B) AGENT resumes automatically once Studio answers (:8888 = 200/30x)
1. **P1-T01 → DONE:** confirm `curl :8888`; get Studio version (`unsloth --version` / doctor); fill `TOOLS.md` header lines 5–6 (server name, URL, version); update `STATUS.md`; commit `P1-T01: …`.
2. **P1-T02:** `unsloth start claude` → verify `studio_status` in `claude` `/mcp`; run `unsloth doctor --mcp` (the P1 exit gate must read OK). Log `logs/tasks/P1-T02.md`; commit.
3. **P1-T03:** MCP logging hook — human reviews `templates/claude-settings.json` + `tools/log_mcp.py` before install (§3.7 consent). **P1-T04:** VRAM sampler + `tools/mcp_report.py`. **P1-T05:** fill `TOOLS.md` MCP table. **P1-T06:** `MODELS.md` + start the big model downloads.
4. **P2-T01..T14:** 15 model smoke tests (write VRAM+time to `logs/`), then ✋ **P2-T15** stack review (human). **P3** CPU tooling against real assets. **P4** pilot + ✋. **P5** pre-prod (✋ lane/script/character/stills). **P6** production (evening hero-shot queue). **P7** post (captions, EDL, mix −14 LUFS, HyperFrames render + mux, ✋ review).
- **Stop at every ✋ and `[HUMAN]` gate. Commit after each DONE/BLOCKED row. One task at a time.**
