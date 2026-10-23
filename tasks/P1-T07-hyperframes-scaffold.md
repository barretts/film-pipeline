# P1-T07 · HyperFrames + render projects

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ human if init is interactive) | P0-T04 | none (CPU) | 20–40 min | — |

**Goal:**
- HyperFrames renders on this PC.
- There are two projects: `render/` for the film and `render_preview/` for previews.
- TOOLS.md holds short notes on the composition rules plus **one canonical render command** that every later task uses.

## Steps
1. Check that `node --version` is ≥ 22.
2. Look for a non-interactive option:
   ```bash
   npx hyperframes init --help
   ```
   - **If there's a `--yes`/defaults flag:** run `npx hyperframes init render` and `npx hyperframes init render_preview` with it, redirecting output to `logs/tasks/P1-T07.out`.
   - **If there isn't:** **[HUMAN]** runs both commands in their own terminal and accepts the defaults.

   Either way, `init` installs HyperFrames' agent skills. Note where they went.
3. Render the starter composition and note where the MP4 is written:
   ```bash
   cd render && npx hyperframes render > ../logs/tasks/P1-T07.out 2>&1; tail -n 5 ../logs/tasks/P1-T07.out
   ```
4. Run `ffprobe` on the MP4. The duration should be > 0 and there should be a video stream.
5. Read only the installed skill's guidance on compositions and rendering. Write a **"HyperFrames notes"** section in TOOLS.md, ≤ 15 lines:
   - how timed elements are declared (`data-start`, `data-duration`, `data-track-index`, …);
   - how width, height and fps are set;
   - what makes an animation seekable;
   - how `<video>` and `<audio>` are handled;
   - the entry file name.
6. In those notes, record the **canonical render command**: run from `render/`, with explicit 1920×1080, 24 fps, quality and output path flags taken from `npx hyperframes render --help`. Write it as `RENDER_CMD: …`.
7. Compare the skill's conventions with `templates/composition_example.html` and note any differences. The skill wins.
8. Commit.

## Outputs
- The `render/` and `render_preview/` HyperFrames projects.
- HyperFrames notes and `RENDER_CMD` in TOOLS.md.

## Done when
- [ ] The starter render produces an MP4 that `ffprobe` reads.
- [ ] The notes and `RENDER_CMD` are written.

## If it fails
- **Node is too old:** run `winget upgrade --id OpenJS.NodeJS.LTS -e`, then open a new terminal.
- **The headless Chrome download is blocked:** check the HyperFrames docs for using an installed Chrome or Edge.
- **`init` refuses because the folder exists:** rename it, run `init`, then move your files back.

## STATUS line
`P1-T07 DONE · render + render_preview ready; RENDER_CMD recorded` (example)
