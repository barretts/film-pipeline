# Directing layer v1 — smallest implementation proposal

Status: PROPOSAL ONLY. No code written. Awaiting owner approval before production integration or any render.

## What the experiments already prove (evidence in jobs/story-{progress-smoke,cut-smoke,next-scene}/)

1. Beat contract works: before/action/after story-state maps + one achievable action + explicit on_screen_cast + dialogue-or-explicit-silence + acceptance list, rendered at 124 frames.
2. Deliberate CUT (new verified guide frame, portrait-only conditioning, first-frame-guide node dropped) achieves departure and persistent absence. Continuation FAILED this (progress-smoke gate correctly rejected both exit takes; runner stopped before downstream beats — failure containment proven).
3. Bounded retry works as designed: reaction take1 rejected (invented background man) → exactly one documented-correction retry → passed. Blind retries impossible (runner requires correction text; max 1).
4. One-action + "completes within this clip, no reset" clause: zero narrative resets in accepted takes.
5. Dialogue = exact reused piper WAVs wired through node 18: assembled correlation 0.9900 / 0.9985 at lag 0; silence = anullsrc fixture, clean.
6. Safety mechanics all held across 6 renders: never-overwrite, queue-busy refuse, interrupt-own-prompt-only, dual locks, Strata kill → /free → finally-restore (restore_exit=0 ×2), original episode hashes unchanged.

## Gaps the experiments did NOT close (assumptions, each gated by tests below)

- Audio correlation + 6/16-frame audits were computed OUTSIDE the runners (ad-hoc). Production must compute them in-runner and attach to the review prompt.
- Nothing validates the state chain: plan.json before == previous beat's after is hand-written. Enforcement = new code.
- The visual gate is a human decision file; sampled frames ≠ every frame (next-scene's calmer-than-requested blizzard became a limitation note, not a gate failure).
- Lip-sync phoneme quality never auditioned; correlation proves placement, not speech realism.
- Untested: continuation chains >2 links, arcs >3 beats, actions needing >124 frames, VLM-assisted absence checks (Strata chat).

## Smallest implementation

New `local_film/directing.py` (~200 lines) + `tools/run_directive.py` (~60 lines) + `tests/test_local_film_directing.py` (~250 lines). ZERO changes to `pipeline.py`/`series.py` (Codex's uncommitted fixes stay owner's to commit) and zero changes to the existing episode-batch path. Experiment runners stay untouched as evidence; their logic is lifted, not rewritten.

1. **Directive schema + validator** — `plan.json` format from the experiments, canonicalized: `{id, initial_state, beats[], max_changed_retries: 1, review_timeout_s, gpu: off|attach|managed}`. Validator: unknown cast slug, dialogue+silence collision, empty acceptance, beat.before ≠ committed current state → refuse before any GPU touch.
2. **Story-state ledger** — `story_state.json` in the job dir, append-only: every take {beat, take, status, before, after, cast_at_end}. Current state derived from last APPROVED take. Completed events persist (state only changes via approved beats). Departure rule: actor in any `missing_*`/offscreen state CANNOT appear in a beat's on_screen_cast unless that beat's before-state explicitly re-enters them.
3. **Graph builder (pure)** — `build_graph(template, beat, cast, guide, audio, seed, prefix)`: clear all `ref_images.*`, rebuild only from on_screen_cast (portrait or orbit refs); `cut: new_location` → drop node 163, rewire 19.positive=['160',0]; `cut: continuation` → tail PNG of previous approved take into node 5 (chained guide); silence → anullsrc 22050-mono 124/24 s; fixed seed/prefix per plan.
4. **Prompt composer** — reuse `S._six_sections`; detail = starting situation JSON + one action + required ending JSON + once-and-completes/no-reset clause + dialogue line ("match only supplied audio") or closed-mouth silence clause; retry appends the documented correction. (Verbatim from proven runners.)
5. **Review gate** — waits for decision JSON {decision: approve|retry|reject, correction, reason, evidence[], limitations[]}; approve advances ledger + guide to tail; retry needs correction, max 1; reject/timeout aborts without rendering downstream beats.
6. **In-runner audits (CPU)** — per take: extract_tail, 6-frame sheet, 16-frame audit grid, and for dialogue beats assembled-vs-source correlation (±1 ms lag search, reuse `P.audio_vector`) → `audit-<beat>-takeN.json` written BEFORE the review prompt. Machine results are advisory attachments; the owner decision file remains the gate (unchanged human authority). Optional VLM absence check behind a flag — OFF in v1 (untested).
7. **Orchestrator + assemble** — queue-busy refuse, dual locks, no-overwrite, interrupt-own-prompt-only, gpu mode `off` default (Strata untouched; `managed` calls the existing kill/restore scripts exactly as experiments did), final `P.assemble`, `result.json` with input SHA-256s + limitations.

## Regression tests (unittest, tmpdir, mocked ffmpeg/api — no GPU, no network)

- Validator: unknown cast; dialogue+silence collision; broken state chain; empty acceptance; retry budget ≠ 1.
- Ledger: approve commits after-state; reject never mutates; stale before → refuse; departed (missing_offscreen) in on_screen_cast → refuse; explicit re-entry beat → allowed.
- Graph: absent cast slots removed, order matches on_screen_cast; new_location drops 163 + rewires 19; continuation sets node-5 guide; silence generates anullsrc (mocked) and wires 18; seed/prefix set; existing take file → error before any API call.
- Prompt: silence beat contains closed-mouth clause and no line; dialogue beat contains line + no-repeat clause; retry adds correction text.
- Gate: approve advances guide to tail; retry requires correction; second retry aborts; reject aborts before next beat; timeout aborts.
- Runner (mocked api): queue busy refuses; interrupt only own prompt_id on timeout; result.json carries input hashes + limitations.
- Audio gate math: identical vector → ~1.0 at lag 0; 1-frame misaligned → below threshold; silent beat skipped.

## Explicitly out of scope (v1)

VLM auto-review; automatic scene composition; >124-frame beats; episode.json batch-path changes; GPU lifecycle changes; committing Codex's uncommitted fixes; ep-2–3 rendering; ep-1 re-assembly decision (separate open question).

## Acceptance when approved

All new tests green + existing 139-test baseline unchanged (3 cv2 errors, 1 skip); a dry-run `run_directive --plan jobs/story-next-scene/plan.json --gpu off --dry-run` validates + builds every graph on CPU and renders nothing; one real 1-beat directive render only after owner green-lights GPU use.
