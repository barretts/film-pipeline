# START HERE: protocol for the implementing agent

You will build and run a local AI short-film pipeline on this PC, one task at a time. This package is sized for an agent with a **~128k-token context**:
- every task file stands on its own;
- progress lives in files, not in your memory;
- a fresh session can always resume.

**Recommended agent:** Claude Code, started in this folder. If you drive it with a local model instead, that model must not use the RTX 4060 Ti. The film's models need the whole GPU.

## 1. Every session

1. **Read:** `CLAUDE.md` (auto-loaded), this file, `CONTEXT.md`, `STATUS.md`.
2. **Pick a task.**
   - If a row is **DOING**, resume it, and read its handoff in `logs/tasks/<ID>.md` first.
   - Otherwise take the first **TODO** row in STATUS.md whose *Needs* are all DONE or SKIPPED. The rows are in working order.
3. **Read only:** that task's phase file (`phases/P<n>-*.md`), its task file (`tasks/<ID>-*.md`), and any files listed under **Read first**.
4. **Start it:** set the row to **DOING**, and start `logs/tasks/<ID>.md` with the date and time.
5. **Do the steps in order.**
   - Record commands, results, measurements and problems in `logs/tasks/<ID>.md`, not in STATUS.md.
   - Steps marked **[HUMAN]**: tell the human exactly what to run or click, then wait for their reply.
6. **Check every box under Done when.**
   - All met: set the row to **DONE** and write a result of ≤ 15 words.
   - Otherwise: set it to **BLOCKED** and give the reason.
7. **Commit** (media and heavy logs are git-ignored):
   ```bash
   git add -A && git commit -m "<ID>: <result>"
   ```
8. **Decide whether to continue.** Start the next task only if context use is below ~50%. If you pass ~60% in the middle of a task, write a handoff (§2) and stop.

## 2. Handoffs and restarts

**When stopping mid-task or ending a session**, append to `logs/tasks/<ID>.md`:
- the step you stopped at;
- what's finished, and the files produced;
- job or queue ids still running;
- the exact next action.

Keep the row **DOING**. The next session resumes from that note.

**When a step needs Claude Code restarted** (new environment variables, new hooks):
1. Write the handoff first.
2. Ask the human to exit and run `claude` again in this folder.
3. Tell the human not to close the Unsloth Studio window or the VRAM sampler window.

## 3. Human checkpoints (✋)

Rows marked ✋ need a human decision:
1. Prepare the review material the task asks for: a contact sheet, a summary table, or a file to watch.
2. Ask a clear yes/no or pick-one question, then stop and wait.
3. Record the decision in STATUS.md › **Decisions**.

## 4. When something fails

1. Follow the task's **If it fails** section.
2. Try at most 3 times per approach, then use the listed fallback.
3. If the fallback also fails, mark the task **BLOCKED**:
   - put the error in ≤ 3 lines in STATUS.md, with full details in the task log;
   - ask the human.
4. Never unblock yourself by changing the model or lane, skipping a QA gate, editing logs, or inventing on-screen text.

## 5. Context hygiene (keeps you inside 128k)

- **Big files:** never `cat`, `tail` or `grep` the MCP logs; use `tools/mcp_report.py`. For other big files, use `tail -n 5` or `head -c 2000`.
- **Noisy commands:** run ffmpeg, npx, pip and renders quietly, or redirect them to `logs/tasks/<ID>.out` and `tail -n 5`.
- **Media:** ask for it as a link or file, always. Look at images only as contact sheets.
- **Batches:** run from manifests in `jobs/`, updating after every item. Per session: ≤ 8 image/video items or ≤ 24 audio takes.
- **Polling:** poll long jobs as CONTEXT §8 says. Summarize each tool response in one line; never paste it whole.
- **Huge results:** if a tool returns something huge, note its seq number (from `mcp_report.py --seq-only`) and move on.

## 6. Status values

- `TODO`, `DOING`, `DONE`, `BLOCKED`
- `SKIPPED`: only if the task says it's optional, or its condition isn't met.

## 7. Phase map

| Phase | Goal | Tasks |
|---|---|---|
| P0 Prepare the PC | Checks, installs, Windows settings, project folder | 4 (mostly human) |
| P1 Install, connect, instrument | Studio + MCP + logging + VRAM measurement + HyperFrames | 8 |
| P2 Smoke tests | Prove every model on this PC; collect fixtures + measurements | 15 |
| P3 Production tooling | Schemas, QA gate, truth-rule facts, mixer, composition builder, mux | 6 |
| P4 Pilot film | 15-second end-to-end run; calibrate | 4 |
| P5 Pre-production | Features from logs → production prompt → shot list → character → stills | 5 |
| P6 Production | Voice, talking/motion/still/hero shots, music, SFX, fine-tune | 9 |
| P7 Post | Captions, EDL, mix, composition, render, review | 6 |

**Estimated elapsed time:** 3–4 days.
- P2 is mostly model downloads (~150–200 GB).
- P6 includes an overnight video queue.
