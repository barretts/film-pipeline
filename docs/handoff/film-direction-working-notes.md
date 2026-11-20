# Working together on a film

Notes from the November 19, 2026 crossing session. These are the owner's stated preferences and examples from one film. Later direction can supersede them.

## What the owner came here to do

“pretend you are me, you want to bring you film.json and run commands, no file editing etc.” That is the test from the filmmaker's seat. Bring a script to an empty project folder. Generate the cast, locations and props; stage the shots in Blender; generate photographic frames and footage; handle dialogue, sound and the edit. Be able to run the whole thing or regenerate one asset or one shot. This session demonstrated a single shot through video. The entire film from a fresh folder remains an open test.

The script creator describes persistent things and how they fit together. Kate's desk receiver and James's handheld have distinct identities. The handheld can start docked in its charger and be carried in a later shot. When the assistant is the director, it can write intent like “start with James at the shut hatch and reveal Kate as he reaches her.” The generator's LLM chooses dimensions, positions, camera travel and timing. The owner expects a fresh take to vary and approved assets to stay stable. A seed can be supplied; the film need not carry one.

The owner's example at the end was changing James's suit to green or making the hatch full height, then watching the change in the footage. That's why the separation between appearance and motion matters.

## How the owner wanted us to work

- **Discuss before acting when asked.** “dont start without talking,” “tell me the list,” and “dont tweak” each gave a clear boundary. When asked for a judgment, open the actual images, say what you see and pause. When asked to investigate, trace the saved inputs and report what the evidence supports.
- **Once given the go-ahead, own the run through the specified stopping point.** “generate just the first frame and test of rcolors” meant one frame. Connecting the Cycles shader, showing that frame, and waiting for the full-render request was a good exchange. “stop after the blender render is complete for us to watch” meant deliver a playable guide and leave the next stage for review.
- **Be clear about who made each decision.** When told “you can only start the generator,” run the real entry point. If a stage is missing, identify it. A one-off request assembled by the assistant can produce an image while invalidating the workflow test. Distinguish film-authored values, model choices, render defaults and inherited inputs when explaining where something came from.
- **Show the artifact the owner is deciding about.** They wanted to look at the generated assets together and cared more about how they came together than seeing pages of descriptions first. Link the exact clip or stills. Compare the same moments. “James stays at the door in both stills” answers a direction question more usefully than praise for the lighting.
- **Keep previous good work.** Reuse frozen sheets when retaking the camera. Keep the same Blender plan when testing render quality. Save an experiment as its own take. When asked to assess Terra's first attempt, save its wording untouched. A request to rerun from the film is a test of the generator's normal path.
- **Give concrete status.** The useful answers named the current sampling step, time per step, measured VRAM owner, or verified output file. Distinguish an assembled graph from a submitted job and a finished MP4. Use the last comparable run to estimate a long job. When asked to clear the GPU, check the queue and verify the released memory.

## Root Cause

The repeated friction came from losing sight of what the run was meant to prove. Designing walk cycles added work when an orange egg had already communicated the crossing. Calling FLUX's first image reference “steering” suggested a stronger camera constraint than the graph provided. The owner repeatedly brought us back to the same question: what did the winning shot actually do?

## Solution Pattern

Agree on the decision for this pass. Preserve the approved inputs, change the relevant stage, and run it through the command the filmmaker would use. Compare the result with the named reference at matching moments. Say what changed on screen, what remains uncertain, and whether the requested stopping point has been reached.

## Recurrence Scan

Reviewed the session's camera, endpoint, and hatch corrections alongside the saved proper-james workflow, crossing room binding, take lookup, and prepare-only command.

| When we worked well together | What to remember |
|---|---|
| The owner asked where the room starts and ends. Comparing guides showed that the winning camera felt inside the room. The floor filled the foreground, the hatch traveled offscreen and Kate appeared as James reached her. | Describe framing in screen terms. Keep the camera inside the room. James staying centered was an observation about that take; the owner later asked for freedom to compose him off-center. |
| The owner asked what we had done differently the best time. The graph saved in the winning MP4 showed H3 receiving the whole Blender clip for motion and separate images for Kate, James and the finished room. | Recover the exact winning inputs before guessing. The independent FLUX stills were useful experiments, but the successful H3 route did not consume them. [Winning workflow and comparison](../minimax-h3/README.md) |
| Comparing the open hatch in the footage with the cabin asset exposed a real input conflict. A sealed-room variant produced a closed hatch. The owner then spotted that its raised sill was also present in the reference. | Inspect the actual selected image. “Closed” and “a person could walk through it” are separate visual checks. [Sealed-room asset](../../TakeFive/films/signal-in-the-snow/crossing-first/asset-library/looks/cabin_sealed.png) |
| The owner wanted faster previews with the Cycles look. A lower internal resolution, GPU denoising and scene reuse kept the lighting and delivered the six-second test in 11.4 seconds. | Report the actual render time. Several settings changed together; the run does not isolate the speedup from any one setting. |

## Automation Opportunity

The crossing now has a command-driven H3 path and a pre-render page showing the two guide frames, exact selected images and final prompt. Use that page before spending an hour on a shot. [Retake review page](../../TakeFive/films/signal-in-the-snow/crossing-first/takes/429f483a7a304ae583c4844bb6a2124e/cross/guided-h3/review.html)

Still proposed: pin an approved camera and motion take while swapping selected art assets. The current take lookup compares the film specification, so an asset edit can cause a new Blender plan. The green-suit experiment was the owner's illustration of desired control, not a completed test.

## Verification

Checkpoint `90e49aa` preserves the work before the sealed-hatch retake. Commit `70a35ea` includes the retake and its inputs. The shot starts with James alone at the hatch and ends beside seated Kate. The sampled opening frames looked cleaner; the cause of the earlier face distortion was never isolated. [Finished crossing](../../TakeFive/films/signal-in-the-snow/crossing-first/takes/429f483a7a304ae583c4844bb6a2124e/cross/guided-h3/video.mp4)
