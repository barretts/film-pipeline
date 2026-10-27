# Start here

This is the single entry point for the local film workflow. Read `CONTEXT.md`, `STATUS.md`, and `handoff.md`; inspect `TOOLS.md` and `MODELS.md` when selecting a tool or model. `brief.md` defines the current film. Resolve differences using fresh evidence and record corrections; do not assume the old phase/task package exists.

## Work and verification

1. Choose the next unfinished outcome from `STATUS.md` and the exact next action in `handoff.md`. Verify the environment and inputs needed for that action. Work on a bounded piece that leaves a useful result.
2. Use local inference for both coding and media. Internet is available for installation, model downloads and research. Select an available local coding client; Strata is optional. Use Unsloth Studio for media when supported, and validate the interface and provenance for the actual client before depending on it.
3. Prove a short pilot with real local media and sound early. Check model fit, timing, output and quality before downloading a large stack or committing to production. Record model identity, settings, output path, evidence and result in `MODELS.md` or `STATUS.md` as appropriate.
4. Keep factual on-screen claims traceable to authentic recorded Unsloth MCP calls or their raw results, per `brief.md`. Never fabricate, repair or hand-author a source log. A client without a verified logging path cannot be assumed to produce claim evidence. Creative text is not an assertion of a product fact.
5. Build the rest of the reusable pipeline from the successful pilot. Review the pilot and final film with the owner. If an element of the brief cannot be produced locally, offer a concrete substitution and get the owner's decision before using it in the final film.

## Switching the GPU and resuming

- Before unloading a local coding model or stopping its client, save files and update `handoff.md` with the current owner/stage, completed work, evidence paths, running jobs, failed attempts, and one exact next action. Update `STATUS.md` with the outcome and state. Do not assume an unsaved conversation survives.
- Inspect GPU memory with `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader`. Unload the active model or stop the competing process when appropriate. The owner has authorized stopping Strata. Do not stop unrelated work without establishing ownership.
- Check that media jobs have finished before unloading a media model. Check available VRAM and Studio's actual model residency before loading the next model; do not rely on old measurements or assume a specific free-memory threshold is enough.
- If a switch requires a human action, give the exact action and expected result. After switching back to coding, read the handoff, inspect outputs and verification evidence, and continue without repeating a completed job.

## Failures and stopping

Record the failed assumption and error. Retry only after changing a relevant condition, at most three attempts per approach. If the approach or a genuine prerequisite remains blocked, state the blocker and its owner, preserve outputs and next action, and continue independent work where possible. A failed, interrupted or unreviewed stage is not complete.

Never print or write credentials. Keep source logs and original media intact. Stop for a required owner decision, for a creative substitution, and for pilot and final-film review. Do not ask the owner to approve ordinary reversible work already authorized by the project request.
