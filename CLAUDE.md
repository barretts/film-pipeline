# Local AI film pipeline (personal lane)

Read `START_HERE.md` and follow its protocol. Then read `CONTEXT.md` and `STATUS.md`, and work on the next task.

Always-on rules (full list in CONTEXT.md §3):
- One GPU model loaded at a time. Local models only, through the Unsloth Studio MCP tools.
- On-screen facts must come from `logs/mcp_calls.jsonl` (truth rule). Never invent numbers; never edit logs.
- Never print, store or ask for the Unsloth API key (`UNSLOTH_API_KEY` env var only); never run `env`, `printenv` or `set`.
- Request media as links/files, never inline. View images only as contact sheets.
- Update `STATUS.md` at the start and end of every task; details go to `logs/tasks/<ID>.md`.
- Stop at ✋ checkpoints and ask the human.
