---
name: workflow
description: Make reviewed local short films with the CPU film-project backend; no account or hosted inference.
---

Use the filmProject tool as the source of truth. The Film Project canvas node is an optional view of the same durable state. Never edit its SQLite database, project artifacts or approvals directly.

1. List/get existing projects before creating another. Create from an explicit spec, or use the supplied Signal in the Snow template. Use stable creationId and commandId values; obtain expectedRevision from get. Retry a lost response with the identical request, never a newly invented id.
2. Draft or update a complete short: an early visual hook, a motivated choice and a payoff. Use registered character ids, one physical action per shot, explicit silence, on_screen/off_screen/radio dialogue sources, continuity states and earlier-shot dependencies. Keep lines short enough to fit. CPU drafting uses the installed local llama.cpp only.
3. Run prepare-assets, then poll get until complete or failed. This measures real Piper speech, creates reference storyboard cards and exports a timed animatic with local sound. Long speech is rejected instead of truncated. Show the local review link. The owner approves the actual storyboard revision; never approve on their behalf or fabricate a review.
4. render-ready prepares immutable request bundles for currently independent/ready shots. This session has GPU execution disabled. Report awaiting-gpu honestly. Do not contact ComfyUI, Studio, cloud image/video APIs, stop services, free VRAM or install alternative media providers. A prepared graph is not a rendered take.
5. In a later GPU session, an operator can bind and obtain human review of required PNG inputs, then separately enable the manual worker, or import existing actual takes. Do not enable it in this CPU session. The owner reviews takes at the local review page. Only approved takes unlock dependent shots. Changed inputs invalidate affected takes and descendants; old media and reviews remain available. An ambiguous submission must be reconciled by its saved UUID; never submit a replacement.
6. Assemble only when all current shots are approved. The backend exports 1280×720 at 24 fps with 48 kHz stereo sound and checks full decode. The owner makes the final film decision separately.

Cancel stops this project's queued CPU work and asks any separately enabled worker to cancel only its owned prompt. GPU cancellation remains pending until confirmed; run that same worker/request again to reconcile after a disconnect. Resume cannot bypass an active or ambiguous request. Closing the canvas or stopping a chat must not cancel production. A failed command, an API success or an output file alone does not establish a finished film. Surface errors and review waits; do not loop unchanged retries. No Toonflow account is required. External requests are allowed for setup/research, but production inference stays local.
