# Local film pipeline

Build and run a film on this Windows PC. The current target is the personal Unsloth Studio promo in `brief.md`; the same workflow should also work with a different brief. Coding and media-model inference must run locally. Internet access is allowed for setup, model downloads, and research.

Start with [START_HERE.md](START_HERE.md), then read [STATUS.md](STATUS.md) and [handoff.md](handoff.md). Those files describe what has actually been done and the exact next action. `CONTEXT.md` holds the constraints, `TOOLS.md` the verified interfaces, and `MODELS.md` the measured model choices.

The project is not a finished film pipeline yet. The first production target is a short pilot that proves a real image or video, sound, and final playable render before committing to the full film. It is not enough to produce a test pattern and call the pilot complete.

A local coding model and media models may take turns on the same GPU. Strata is optional; the owner has authorized stopping it when its resources are needed. Persist work before switching. See `START_HERE.md` for the handoff and recovery procedure.

## Unattended local film jobs

For the local prompt form, offline planner and voice, MiniMax H3 speech-driven rendering, continuations, assembly and review reports, see [LOCAL_FILM_INSTALL_GUIDE.md](LOCAL_FILM_INSTALL_GUIDE.md). Start the form with `python -m local_film.server` after setting up the isolated dependencies. The guide distinguishes the tested machine from untested fresh-machine installation steps. Older workflows remain available.

For a short, practical walkthrough, see [HOW_TO_MAKE_A_VIDEO.md](HOW_TO_MAKE_A_VIDEO.md).
