# Phase 1: Install, connect, instrument

**Goal:** Unsloth Studio is running and Claude Code is connected to its MCP server. Every MCP call is logged automatically, VRAM is sampled continuously, the available tools and models are documented, HyperFrames renders, and the contact-sheet tool works.
**Who:** the human for Studio setup and the API key; the agent for everything else.
**Time:** 2–4 h. Model downloads start in P1-T06 and continue into P2.

## Tasks
| ID | Task | Who | Notes |
|---|---|---|---|
| P1-T01 | Install and start Unsloth Studio | HUMAN | owner account, memory settings |
| P1-T02 | Turn on MCP, connect Claude Code | HUMAN + AGENT | API key goes in an env var only |
| P1-T03 | MCP logging hook | AGENT | provided script `tools/log_mcp.py` |
| P1-T04 | VRAM sampler + MCP report | AGENT | you write 2 small scripts |
| P1-T05 | Discover MCP tools → TOOLS.md | AGENT | keep TOOLS.md compact |
| P1-T06 | Map models to the catalog → MODELS.md | AGENT | start big downloads |
| P1-T07 | HyperFrames + folder scaffold | AGENT | Node 22+ |
| P1-T08 | Contact-sheet tool | AGENT | needed for every visual review |

P1-T07 and P1-T08 depend only on P0-T04, so you can do them while waiting for the human in P1-T01 and P1-T02.

## Exit criteria
- `unsloth doctor --mcp` reports Verdict OK, and `studio_status` works from Claude Code.
- Every MCP call adds a line to `logs/mcp_calls.jsonl`, with no secrets in it.
- `tools/mcp_report.py --last 5` prints durations and peak VRAM.
- TOOLS.md and MODELS.md are filled in.
- `npx hyperframes render` produces an MP4.
- `tools/contact_sheet.py` makes a sheet from images and videos.

## Security notes
- The Unsloth API key (`sk-unsloth-…`) is a credential. Keep it in the user env var `UNSLOTH_API_KEY` only.
  - If it ever appears in chat, a file or a log, the human rotates it in Studio › Settings › API.
- Hooks run commands on this PC. The human reviews `templates/claude-settings.json` and `tools/log_mcp.py` before they are installed (P1-T03).
