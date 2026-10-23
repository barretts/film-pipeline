# Phase 0: Prepare the PC

**Goal:** the PC passes the readiness check, all prerequisites are installed, Windows is set up for big model files, and the project folder has a Python venv and git.
**Who:** mostly the human. Claude Code can't run until P0-T02 is done, so the human does P0-T01 to P0-T03 by hand by following the task files.
**Time:** 1–2 h.

## Entry
- This package has been unzipped on the PC.

## Tasks
| ID | Task | Who |
|---|---|---|
| P0-T01 | Hardware check | HUMAN |
| P0-T02 | Install prerequisites | HUMAN |
| P0-T03 | Windows settings + model drive | HUMAN |
| P0-T04 | Project folder, venv, git | AGENT (first agent task) |

## Exit criteria
- `tools/check-film-pc.ps1 -ModelDrive X -Json` shows no `[FIX]` lines.
- `git`, `node` (≥ 22), `ffmpeg`, `py -3.12`, `claude`, and `unsloth` all run from a new terminal.
- The project folder sits on the model drive. `.venv` imports numpy, soundfile, librosa, PIL and jsonschema. `git log` shows the first commit.

## Notes
- If IT manages this PC, confirm you're allowed to install software and download model weights before starting.
- Windows 11 runs fine on Zen 1 (Threadripper 1950X). Nothing special is needed.
- Close games, overlays and GPU-accelerated browser tabs during long runs; they take VRAM.
