# Sol handoff — November 20, 2026

Read the [working notes](film-direction-working-notes.md) first. The owner wants to bring a film specification, run commands, and review the result at the stage they requested. Terra remains the pipeline planner when Sol operates the CLI.

## Where to resume

The [film](../../TakeFive/films/signal-in-the-snow/crossing-first/film.json) and [finished crossing](../../TakeFive/films/signal-in-the-snow/crossing-first/takes/429f483a7a304ae583c4844bb6a2124e/cross/guided-h3/video.mp4) are the baseline from commit `70a35ea`. The [review page](../../TakeFive/films/signal-in-the-snow/crossing-first/takes/429f483a7a304ae583c4844bb6a2124e/cross/guided-h3/review.html) shows the inputs. H3 rendered the six-second crossing in about 53 minutes. The sealed hatch looks raised in both the room asset and the video.

From the repo root, the preparation command is:

```powershell
TakeFive/Directed-Film.cmd TakeFive/films/signal-in-the-snow/crossing-first/film.json video cross --prepare-only
```

## Proposed next test

When the owner asks to proceed, add support for pinning an approved guide across an appearance edit. Current take lookup compares the whole film specification. Change James's suit to green in a separate asset variant, preserve the existing red take, and prepare the new H3 job. Compare the SHA-256 of its steering input against the approved clip and inspect its actual selected images and prompt. Matching guide bytes establish identical input motion; the resulting footage still needs visual review. This handoff itself does not request a new render.
