# CPU film workflow

This is the account-free, local preparation path for a reviewed short film: CPU llama.cpp, Piper voices, reference storyboard cards, and software FFmpeg. The CPU launcher never starts the legacy render queue or changes GPU services.

## Start and review

From `F:\film-pipeline` in PowerShell:

```powershell
.\.venv\Scripts\python.exe tools/start_cpu_film.py --setup-only
.\.venv\Scripts\python.exe tools/start_cpu_film.py --skip-build
```

Setup builds and typechecks the supported Toonflow extension against the evaluated upstream commit. It uses installed SDK dependencies, a separate profile in `local-runtime/film-toonflow`, and ignored build files. It refuses an unrelated existing profile or a different upstream revision.

Open [local film review](http://127.0.0.1:8766/) or [local Toonflow](http://127.0.0.1:33030/). No account is required. If Toonflow offers account onboarding, choose **Set up later**. Select **Local CPU**, open the `films` workspace and its `filmProject.json` canvas. Setup creates that canvas once and preserves subsequent edits. When the prepared Signal project exists, its node is linked already.

The review page contains the script, timing animatic, reference cards, take reviews and export. The canvas node and paired `filmProject` agent tool use that same backend state. Closing a chat or canvas does not cancel queued CPU work.

Stop only this profile's CPU services with:

```powershell
.\.venv\Scripts\python.exe tools/start_cpu_film.py --stop
```

Ctrl+C in the foreground launcher also stops its services. The backend stops active CPU children before exiting; interrupted work retains its command record and has bounded recovery. To run only the review/preparation backend, use `--backend-only --skip-build`. Stop that instance before starting the full profile on the same ports.

## Workflow and state

```mermaid
flowchart LR
    Brief[Brief and registered cast] --> Draft[Script and shots]
    Draft --> Prepare[CPU voices, sound and timing cards]
    Prepare --> Animatic[Timed animatic]
    Animatic --> Owner[Owner storyboard review]
    Owner --> Requests[Ready shot request bundles]
    Requests --> GPU[Later GPU execution phase]
    GPU --> Takes[Imported takes and end frames]
    Takes --> Review[Owner take review]
    Review --> Requests
    Review --> Assemble[CPU assembly]
    Assemble --> Final[Owner film review]
```

- `examples/signalInTheSnow.json` is the separate 38-second short revision. The early warning, James's choice and Kate transmitting the opening line provide its hook and payoff. Creative effectiveness remains an owner judgment. Existing series and media are preserved.
- Specifications distinguish visible/off-screen cast, radio voices, silence, speech offsets, single-shot actions, dependencies and before/after states. Dependencies must precede their consumers. Contradictory states are rejected; a character whose state is `gone` needs `re_entry_cast` before returning.
- Approved registry portraits/references and voices are hashed. Verified recordings persist across revisions, preserving unchanged audio when a camera or prompt changes. Speech is measured and rejected if it will not fit, rather than shortened. The opening/closing warning reuses one recording. Radio/off-screen voices and sound effects stay out of lip-sync conditioning.
- The animatic uses reference portraits and labeled planning cards with sound. It is a timing/review artifact; generated film footage is deferred.
- SQLite in `film-projects/` owns project revisions, commands and reviews. Each CPU attempt writes a separate directory. Published artifacts carry hashes and are never overwritten. Old takes and reviews remain accessible when their inputs become stale.
- Only approved current takes unlock dependents. One changed retry needs human authorization tied to its input hash; two rendered/imported takes per shot are the limit. Repeating an unchanged request does not create another take.
- Submitted attempts consume that limit even if the server rejects the graph or no output is recovered. Unknown outcomes block further dispatch until the saved request is reconciled.
- CPU assembly normalizes approved video, uses the prepared soundtrack, exports H.264 1280×720/24 fps with stereo 48 kHz AAC, checks duration and fully decodes both streams. Final approval is separate.

The CPU server never submits GPU work. `render-ready` saves versioned H3 requests and their required inputs, then waits. A separate disabled-by-default worker is implemented and tested with simulated responses. The templates no longer read historical `source_job` graphs. Dialogue needs a composed first frame; action uses image references without a character blockout guide. Approved imported end frames are supplied as action references and shown for dependent frame composition/review.

The owner approved Signal's story and timing on 2026-11-17. The saved project is `film-14ce7ba2-c038-5358-93e9-24fb786d0a27`, revision 10, `awaiting-gpu`: two independent request bundles, no submitted or rendered takes. Its 38-second animatic is unchanged. This approval does not enable GPU execution or approve generated images, shots or the final film.

## Interfaces

The loopback API on port 8766 provides:

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/film/v1/capabilities` | CPU policy; account requirement |
| GET / POST | `/api/film/v1/projects` | List/create; creation needs stable `creation_id` plus `spec` or the Signal template |
| GET | `/api/film/v1/projects/:id` | Revision, commands, ready shots, reviews and artifacts |
| POST | `/api/film/v1/projects/:id/commands` | Apply or queue a command |
| GET | `/api/film/v1/projects/:id/artifacts/:artifactId` | Hash-verified artifact; video byte ranges |
| GET | `/film/projects/:id/review` | Local human review page |

Commands have `{command_id, expected_revision, action, payload}`. Agent actions are `draft`, `update`, `prepare-assets`, `render-ready`, `assemble`, `cancel`, and `resume`. Identical request IDs return the original acknowledgment; conflicting content or an outdated revision is rejected. UIs retain interrupted requests for replay. CPU recovery is limited to two worker attempts and cannot repurpose an old command for changed inputs.

The agent interfaces cannot approve storyboards, required image inputs, takes, retries or the final film. Those actions use the local review session. This is an application review gate in a trusted local installation; server plugins retain their normal host permissions.

Operator CLI examples:

```powershell
.\.venv\Scripts\python.exe -m local_film.project_cli create examples/signalInTheSnow.json --creation-id my-short-v1
.\.venv\Scripts\python.exe -m local_film.project_cli get PROJECT_ID
.\.venv\Scripts\python.exe -m local_film.project_cli command PROJECT_ID prepare-assets --revision REVISION --command-id prepare-v1
.\.venv\Scripts\python.exe -m local_film.project_cli work
.\.venv\Scripts\python.exe -m local_film.project_cli import-take PROJECT_ID TAKE_ID F:/path/to/take.mp4 --revision REVISION
.\.venv\Scripts\python.exe -m local_film.project_cli bind-input PROJECT_ID TAKE_ID REQUIRED_INPUT_NAME F:/path/to/frame.png --revision REVISION
```

Importing is an explicit local operator action. It checks shot duration and video decode, publishes an immutable copy, extracts the last decoded frame, and waits for human review. The HTTP/agent API cannot import arbitrary filesystem paths. `bind-input` accepts a required composed-first-frame or room-reference PNG at 1280×704. It preserves previous bindings as artifacts and clears image approval when the selected bytes change. Approve the bound image on the local review page; that approval never starts inference.

## Verification

```powershell
.\.venv\Scripts\python.exe tools/verify_cpu.py
.\.venv\Scripts\python.exe tools/start_cpu_film.py --setup-only
.\.venv\Scripts\python.exe tools/verify_toonflow_cpu.py
```

Stop this profile's services before the full HTTP-agent verifier; it needs their ports. It starts its own CPU services, exercises the actual Toonflow agent endpoint and film tool, records the stream, then stops its services. The regression runner isolates writes, rejects GPU/lifecycle processes and non-test network connections, and allows software FFmpeg/FFprobe only. Full output and a machine-readable summary are saved together.

The dedicated profile has a compact local prompt and 16k CPU context. The stock 8k configuration exhausted its response budget in the full agent check. This separate profile installs the local workflow and film/canvas/question/skill tools. It does not install hosted media providers or browser execution tools. Ordinary external setup/research requests remain allowed.

## Deferred GPU phase

Keep GPU residency and services untouched under the present instruction. Storyboard approval is recorded; actual image and shot generation is still deferred.

`local_film.project_gpu` is the separate opt-in worker. It shares `local-film-jobs/pipeline.lock` and `gpu.lock`, persists its canonical prompt UUID/client/graph/input manifest before submission, checks ownership in queue/history, and imports a completed video without resubmitting it. A missing submission response, ownership mismatch, missing output or unconfirmed cancellation retains the reservation. Run the same worker/take again to reconcile; never invent a replacement request. A prompt absent from both queue and history stays unresolved and needs operator inspection. The code uses ComfyUI's atomic per-job cancellation route; it has no global interrupt.

This worker expects an already running local ComfyUI with explicit local input/output directories. It never starts/stops services, frees model memory, or pauses Strata. Resource switching remains an operator action for the later authorized GPU phase; there are no adapter-paused resources to restore. Locks are released at the review wait. The CPU launcher and Toonflow tool cannot enable the worker.

Future operator command, **only after the owner authorizes GPU use and the required images are reviewed**:

```powershell
.\.venv\Scripts\python.exe -m local_film.project_gpu PROJECT_ID TAKE_ID --enable-gpu --input-root F:/film-pipeline/comfy-local/input --output-root F:/film-pipeline/comfy-local/output
```

The default endpoint is loopback port 8191; `--origin` permits another loopback HTTP origin. This command was not executed against a real GPU server during CPU work. Its protocol/ownership/recovery cases were tested with fakes and an ephemeral HTTP test server. See `docs/handoff/cpuFilmSession.md` for evidence and the later pilot checklist.

The later GPU phase must prove a real landscape speech shot and a reference-driven action shot, generate/review composed first frames and room references, and obtain owner review. No real GPU submission/recovery/cancellation or final generative-film quality is claimed by these CPU checks.
