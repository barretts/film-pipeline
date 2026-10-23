# film-pipeline: quick start for you (the human)

This folder holds the phase and task files that let an AI coding agent build and run the local AI short-film pipeline on this PC:
- personal lane;
- RTX 4060 Ti 16 GB, Threadripper 1950X, 128 GB RAM.

It is written for agents with a **~128k-token context**. Each session loads only ~10k tokens of instructions, and all progress lives in `STATUS.md`.

## How to start
1. Copy this folder to your model drive, using a short path such as `X:\film-pipeline`.
2. Do the three setup tasks yourself by following their files; Claude Code isn't installed yet:
   - `tasks/P0-T01-hardware-check.md`
   - `tasks/P0-T02-install-prerequisites.md`
   - `tasks/P0-T03-windows-settings.md`

   Mark them DONE in `STATUS.md`.
3. Open a terminal in this folder, run `claude`, and say: **"Read START_HERE.md and continue."**
4. The agent works through `STATUS.md` one task at a time. It stops for you at **✋ checkpoints**, and when a step needs you to click or run something (marked [HUMAN]).

## What you'll be asked to do
| When | What |
|---|---|
| P1-T01/T02 | Start Unsloth Studio; create an API key and store it in the `UNSLOTH_API_KEY` user env var (never paste it into chat) |
| P1-T03 | Approve the logging hook (it only writes to `logs/`) |
| P1-T04 | Keep the VRAM sampler window open until the end |
| P2-T15 ✋ | Approve the model stack after the smoke tests |
| P4-T04 ✋ | Watch the 15-second pilot; approve look, voice, pacing |
| P5-T03/T04/T05 ✋ | Approve the script, pick the character, approve the stills |
| P6-T01 ✋ | Approve her voice |
| P6-T05 | Leave the PC on overnight for the hero shots |
| P7-T06 ✋ | Watch the final film; approve or list fixes |

## Good to know
- **Elapsed time:** about 3–4 days, with ~150–200 GB of model downloads and one overnight render queue.
- **Licenses:** Qwen-Image-2.1-Turbo, Breeze-TTS-2 and YuE 2 are non-commercial, and LTX-2.5 uses its community license. **Treat the film as personal, non-commercial.**
- **Truth rule:** every on-screen fact comes from the real MCP call logs (`logs/mcp_calls.jsonl`). `tools/facts.py` checks them before rendering.
- **Restarting:** to pause or restart, just start a new `claude` session in this folder. The agent resumes from `STATUS.md` and the handoff notes in `logs/tasks/`.

## Folder map
```
README.md (this) · START_HERE.md (agent protocol) · CONTEXT.md (facts & rules) · STATUS.md (progress)
brief.md (the film) · TOOLS.md / MODELS.md (filled in by the agent)
phases/ (8 phase files) · tasks/ (57 task files) · templates/ (schemas, hook settings) · tools/ (scripts)
```
