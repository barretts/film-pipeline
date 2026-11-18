# CPU film workflow handoff

Written 2026-11-17 against branch `phase0-rigid-llm`, HEAD `7f82238654b6af74e4bff1f6099a3e012c7e67d1`, plus uncommitted implementation. The worktree was dirty before this goal. CPU-only implementation and checks are complete; the generative film and real GPU integration remain unproven. No commit was requested or made.

## Objective

Complete the CPU-only parts of the agreed Toonflow/short-film plan while preserving the owner's GPU workload. Keep production local/account-free. Expert `expert-orchestrator-simon` is active. No subagents were requested or spawned.

The real short is `film-14ce7ba2-c038-5358-93e9-24fb786d0a27`, revision **10**, `awaiting-gpu`: owner-approved story/timing, two prepared requests, **zero submitted/rendered takes**, no bound production images. Read it without rendering:

```powershell
.\.venv\Scripts\python.exe -m local_film.project_cli get film-14ce7ba2-c038-5358-93e9-24fb786d0a27
```

The CPU entry point is `tools/start_cpu_film.py`. The older `local_film.server` can dispatch GPU jobs. Preserve legacy pipeline/series/directing changes, character data and experiment logs that predate this goal.

## Procedure

Implemented stages and their gates:

1. **Specification and drafting:** `project_contract.py` validates cast, duration, dialogue sources, silence, dependencies and continuity. `project_writer.py` uses local CPU llama.cpp, schema output, at most two corrections with the failed answer/feedback, saved raw responses and owned-process cancellation.
2. **Preparation:** `project_media.py` uses real Piper timings, persistent hash-verified recordings, separate on-screen conditioning, local sound cues and planning cards. It produces a timed animatic without generating GPU imagery. Unchanged recordings survive camera edits.
3. **Durable control and review:** `project_store.py` and `projects.py` use SQLite revisions, stable command IDs, bounded CPU recovery, immutable artifacts, selective invalidation and human-only approval actions. `project_server.py` provides loopback/origin checks, ranges and local review. The agent cannot approve on the owner's behalf.
4. **Requests and required images:** `project_graphs.py` builds versioned H3 speech/action graphs without historical `source_job` reads or character blockout guides. `project_inputs.py` imports immutable 1280×704 PNG bindings; the owner separately reviews their exact bytes. Approved parent end frames are action references and are shown for dependent frame composition.
5. **Separate execution adapter:** `project_gpu.py` requires explicit opt-in, an existing loopback ComfyUI and local input/output roots. It shares legacy GPU/pipeline locks, persists UUID/client/graph/input identity before submission, verifies queue/history ownership, reconciles ambiguity, cancels atomically by job ID, and imports recovered outputs without resubmission. Tests use fakes and an ephemeral HTTP server. Submitted failures consume the two-take budget even without output. Unknown outcomes retain a reservation and block further dispatch.
6. **Take review and assembly:** imported video must cover its shot and decode; immutable publication extracts the last frame. Only owner-approved current takes unlock dependents. One changed retry requires owner authorization; two submitted/imported takes per shot is the limit. Software FFmpeg assembly uses the prepared soundtrack, normalizes delivery and checks full A/V decode. Final approval is separate.
7. **Toonflow:** `integrations/toonflow/` supplies a supported Film Project node, paired SDK tool, compact local prompt/workflow and dedicated profile; no upstream fork. Content revisions synchronize rebuilt plugins. The approved final video is the node's output.

The CPU server/tool never enable the manual worker. The worker never starts/stops services, unloads models, inspects VRAM or pauses Strata. Resource switching is a later operator action; there are no adapter-paused resources to restore. Live-worker locks are released before human review. No real opt-in hardware path ran.

The PDF's contracts, local front end, CPU voice/animatic, shot review and deterministic assembly are covered by this scoped implementation. The agreed H3/Piper path reuses the existing back half. Alternative video models, Blender guide automation, extra editors and VLM policy remain decisions informed by real pilots. Automating unproven lanes was not treated as CPU completion evidence.

## Stopping Conditions

The CPU-only success condition is reached: guarded regressions, actual CPU inference/media/agent checks, build/types, software browser checks and production state are recorded. Do not continue by consuming GPU memory under the current instruction.

Later production order, only after the owner authorizes GPU use:

1. Arrange resources and confirm the intended local server/input/output roots. The new worker has no Strata lifecycle or memory-freeing operations; do not invoke old lifecycle helpers implicitly.
2. Generate/review the radio room reference and James composed first frame for the two ready requests. Bind each PNG through `project_cli bind-input`, then approve it on the review page. Production inputs are still unbound.
3. Prove one real landscape speech shot and one reference/action shot through the opt-in worker. Re-check node/model fit, UUID ownership, targeted cancel and recovery. Record time, settings and output. Fake tests do not establish hardware compatibility.
4. Stop for owner take review. Approvals unlock dependent shots and supply their end frames. Unknown outcomes must reconcile by the same UUID; absence alone never permits a replacement. At two submitted/imported attempts, stop and revise the approach.
5. Finish the seven-shot graph, assemble, inspect/listen for continuity and lip sync, and obtain final approval. Revisit optional lanes only for a demonstrated need.

Local source inspection of `E:/SwarmUI/dlbackend/comfy/ComfyUI/server.py` found canonical client-supplied `prompt_id` support and `/api/jobs/{id}/cancel` using atomic `interrupt_if_running(prompt_id)`. The adapter uses that per-job route after ownership verification. It never calls global `/interrupt` or `/free`. This was source inspection and simulated HTTP testing, not contact with the GPU server.

## Procedure Risks

- The owner approved **“Approve story and timing”** on 2026-11-17. Commands `ownerStoryboard20261117` and `prepareApprovedSignalRequestsV1` record approval and request preparation. This does not authorize GPU use or approve images, takes or the final film.
- The active animatic SHA-256 is `9b6370cd5efc1116e8936aec55af1681be269d721ad914ca6ee53088bba6af81`, identical to the owner-viewed version. It remains at `film-projects/film-14ce7ba2-c038-5358-93e9-24fb786d0a27/commands/prepareEstablishedStyleV2/attempt-1/animatic.mp4`.
- The verified animatic fully decodes at 1280×720/24 fps, 48 kHz stereo, about 38.04 seconds. It contains labeled planning cards, approved portrait references, real voices and sound cues. It is not generated film footage.
- Historical creation content differs from the current style-corrected specification. Fetch by ID; recreating the old creation ID with the updated example intentionally conflicts.
- All verifier-owned CPU services and software browser were stopped. A session JSON alone is not proof of a running process. Do not stop a process merely because it uses a familiar port.
- Build commands needed elevation because sandbox/real-user Windows ownership differs. Do not change ACLs or global Git configuration. The launcher uses a per-command safe-directory exception for the pinned Toonflow checkout.
- Runtime/evidence under ignored `film-projects/` and `local-runtime/` is not source to commit. Preserve raw logs, existing media, old reviews and preexisting dirty work.

## Evaluation

Paths below are relative to `film-projects/verification/` unless noted.

| Check | Verified result and evidence |
|---|---|
| Guarded regressions | **219 tests, zero failures/errors/skips and zero blocked operations**, `cpu-suite-final/summary.json` and `unittest.log`; software FFmpeg/FFprobe only. Pattern covers local-film plus MiniMax speech tests, not every GPU-dependent repository test. |
| Build/types | `tools/start_cpu_film.py --setup-only` passed Vue/TypeScript checks and built node/tool. Vendor is pinned to `6086cdffceb704a632eca143dd16cd461a78cdac`. |
| Actual CPU agent | `toonflow-20261117-003522/summary.json`: actual HTTP agent used installed filmProject, returned saved ID/status without an account, no errors, installed/build hashes match, no media providers. All three owned service ports closed; launcher exited 0. Raw stream is `agent.ndjson`. |
| Installed tool writes/replay | `tool-write-20261117-000921/summary.json`: isolated create/prepare through installed SDK tool; identical request replay kept one command/preparation. |
| Review UI | `browser-review-20261117/summary.json`, `browser-result.json`: isolated fixture, headless browser with GPU/WebGL/hardware-video paths disabled; actual software playback, image approval, dirty-edit preservation, changed-spec gate, storyboard approval, desktop/390px mobile. Screenshots visually inspected. Requests stayed on the fixture origin; browser/server stopped. |
| CPU writer | Earlier live smoke `writer-20261116-232033/summary.json`, draft and raw responses: valid three-shot, 30-second draft. It is isolated, not a replacement short. Later repair/context changes have unit coverage; do not claim every repair branch was exercised by that older live run. |
| Import/dependency/export | `import-assembly-20261116-232033/summary.json`: two CPU technical stand-ins, imported end frames, approved parent frame in dependent request, complete 10-second export. Fixture approvals are simulated, not production approval. The final suite additionally exercises import/decode/output recovery. |
| Voice preservation | Same fixture's `voice-reuse.json`: camera-only edit, zero Piper launches, exact old audio hashes, unaffected parent approval preserved and edited dependent invalidated. |
| Model-file preflight | `localModelFiles.json`: all 12 template model references were local; presence only, no model loaded. |
| Real preparation | `productionRevision2.json`: revision 8 at preparation time, four persistent voice recordings, same 38-second animatic bytes, no GPU work. |
| Owner decision/requests | `ownerStoryboardApproval.json`: explicit reply recorded against the same animatic hash, revision 10, two request artifacts, no submitted/rendered media; process/network calls blocked and none attempted during that update. |

The earlier full-agent run reported revision 4. The latest full-agent check reported revision 8 before the owner's reply. Saving approval and requests advanced production to revision 10. A fresh `get` is authoritative.

## What could not be verified

- Real submission/recovery/cancellation against ComfyUI hardware: transport code and simulated HTTP checks are complete, but hardware calls were forbidden. Later pilots must prove compatibility.
- Landscape graph execution, node/model compatibility, fit, rendered image quality, perceived lip sync and continuity. File presence and CPU technical clips do not establish these.
- Generated-image/take/final-film approval. Storyboard/timing approval is complete.
- Every upstream Toonflow UI screen and canvas drag/drop. The review UI was browser-tested; the node was built/typechecked and actual SDK/agent integration was checked separately.

## Corrections to earlier assumptions

1. Build success and a plain model reply did not prove the agent loop. Actual HTTP agent and installed-tool checks now provide that narrower evidence.
2. Stock 8k context truncated after its large prompt. Compact tools/workflow and 16k CPU context passed; do not restore the stock prompt for local H3.
3. Rebuilding did not update initialized plugins. Content revisions and installed/build hash checks fixed that.
4. Windows dropped clients could raise ConnectionAbortedError despite green tests. The handler catches ConnectionError, regression asserts no handler exception, and saved logs capture stdout/stderr.
5. Regenerating all voices changed unaffected inputs. Persistent verified recordings and a real camera-only revision now preserve exact bytes.
6. Early “illustrated” style conflicted with established realism. It was corrected before GPU generation; the timing animatic stayed byte-identical.
7. Imported-video count missed failed submitted attempts. The cap now counts submissions without recovered media. Cancellation stays pending until the owned computation stops; crashed preflight can be cancelled without submission.
8. The first checkpoint left execution wiring unfinished. Worker/image review are now implemented and CPU-tested, with GPU dispatch disabled by default. Real landscape H3 feasibility is still unproven.
