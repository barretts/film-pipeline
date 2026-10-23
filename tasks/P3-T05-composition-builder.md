# P3-T05 · Composition builder: `tools/build_composition.py`

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P3-T03 | none (CPU) | 2–3 h | — |

**Goal:** generate the HyperFrames composition from the EDL, the facts and the captions, so the edit is reproducible and every on-screen fact is checked.

**Read first:** TOOLS.md › HyperFrames notes (its conventions win); `templates/composition_example.html`; `templates/edl.schema.json`.

## Spec
- **Usage:** `build_composition.py --edl edit/edl.json --facts edit/facts.json --out render/ [--captions-dir captions] [--only START-END]`
- **Previews:** `--only` must be used with `--out render_preview/`. The builder refuses `--only` together with `--out render/`, so the full composition is never overwritten by a fragment.
- **What it writes:**
  - the composition entry file named in the HyperFrames notes;
  - the assets it uses, copied or hard-linked into `render/assets/` (skip a file if it's unchanged).
- **Video track:** one `<video>` per EDL video item:
  - `data-start` and `data-duration`, a track index, and the in-point and playback rate in the way HyperFrames supports;
  - muted, `object-fit: cover`;
  - transitions (`fade_from_black`, `dissolve`) as **seekable** opacity animations, using CSS or GSAP as the notes require.
- **Text overlays** (title, subtitle, label):
  - text comes **only** from `facts.json`, through `fact_ref`;
  - every resolved string is run through the same logic as `facts.py check`;
  - **stop with exit 1** if a ref is missing or a check fails;
  - style: serif, wide letter-spacing, bone white `#efe9dc` on picture, with slow fades.
- **`chalk_curve`:**
  - an inline SVG polyline built from the overlay's `data_file` (a `step,loss` CSV), scaled to the board area;
  - drawn on with `stroke-dasharray`/`stroke-dashoffset` over the overlay duration (seekable);
  - an off-white chalk look with a light `feTurbulence` displacement filter, and no axes or numbers unless they come from facts.
- **Captions:** from `captions/<id>.json` word timings. Each word appears at `start + (t − in)` from its EDL caption entry; words with t < in are dropped. Lines are ≤ 42 characters, at the bottom, with soft fades.
- **Film-wide:** a grain and vignette overlay (static texture, or seekable stepped animation), and black at both ends.
- **No audio elements.** The mix is muxed later.
- **`--only START-END`** builds just a time window, for quick previews.
- **Output:** print counts per element type, total duration and assets copied.

## Steps
1. Write the script.
2. Build `tests/samples/edl_pilotlike.json` (~10 s) from the fixtures. Include a dissolve, a title overlay with a valid `fact_ref` (from P3-T03), a `chalk_curve` overlay using `tests/fixtures/loss_test.csv`, and one caption file. Make the caption file yourself from `clone_t1`'s MOSS transcript.
3. Build it into `render_preview/`, then render with `RENDER_CMD` from TOOLS.md, run inside `render_preview/` and redirected to `logs/tasks/P3-T05.out`:
   ```bash
   .venv/Scripts/python tools/build_composition.py --edl tests/samples/edl_pilotlike.json --facts edit/facts.json --captions-dir tests/samples --out render_preview/
   ```
   Check the result with `ffprobe`, then make a contact sheet at 0.2, 0.5 and 0.8 and view it.
4. Negative test: a `fact_ref` that doesn't exist must stop the build with exit 1 and a clear message.

## Outputs
- `tools/build_composition.py`; a preview render; the negative test recorded in the task log.

## Done when
- [ ] The preview renders and shows the clip, the title, the drawn chalk curve and the captions.
- [ ] The bad fact_ref stops the build.

## STATUS line
`P3-T05 DONE · builder renders preview; bad fact_ref aborts` (example)
