# P7-T04 · Composition (HyperFrames)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P7-T02 | none (CPU) | 30–60 min | — |

**Goal:** the full HyperFrames composition, built from the EDL, with every on-screen fact verified.

## Steps
1. Build it:
   ```bash
   .venv/Scripts/python tools/build_composition.py --edl edit/edl.json --facts edit/facts.json --out render/
   ```
   The builder runs the facts check on every overlay and stops if one fails.
2. Preview two risky windows with `--only START-END --out render_preview/`. Render each with `RENDER_CMD` inside `render_preview/`, output redirected to `logs/tasks/P7-T04.out`. Then make a contact sheet:
   - the classroom shot with the chalk curve;
   - the busiest title-card stretch.
3. Check:
   - the chalk curve draws on over the shot and follows the loss shape;
   - titles are readable, centered and fade in and out;
   - captions don't collide with titles;
   - transitions are smooth.
4. Fix problems in the EDL (timings, positions) or in the builder's styles, then rebuild. If you changed the builder, re-run its P3-T05 tests.

## Outputs
- The full composition in `render/`, plus preview sheets.

## Done when
- [ ] The full build exits 0.
- [ ] Both previews look right.

## STATUS line
`P7-T04 DONE · composition built; chalk curve + titles verified` (example)
