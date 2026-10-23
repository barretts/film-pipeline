# Phase 3: Production tooling

**Goal:** small, tested scripts for the deterministic parts, so the creative phases can't drift:
- schema validation
- batch manifests
- the voice QA gate
- the truth-rule facts checker
- the audio mixer
- the HyperFrames composition builder
- the final mux

**Who:** the agent (coding). No GPU models are needed, apart from optional checks.
**Time:** 3–6 h.

## Coding standards (all P3 scripts)
- **Runtime:** Python 3.12 in `.venv`. Use only the standard library and `tools/requirements.txt`. No network calls.
- **CLI:** use `argparse` with `--help`. Exit 0 on success, 1 on failure, 2 on bad usage.
- **Output:** print a compact summary of ≤ 40 lines. Use `--json-out PATH` for machine-readable results, so the agent never needs to read long output.
- **Paths:** relative to the project root. Forward slashes work on Windows.
- **Size:** one script per job, ≤ 400 lines each, with a module docstring that states inputs and outputs.
- **Testing:**
  - Test on `tests/fixtures/` (from P2) and on synthetic inputs you generate, such as `ffmpeg -f lavfi -i sine=…` or `testsrc`.
  - Put each test command and its result in the task log.

## Tasks
| ID | Script(s) | Used in |
|---|---|---|
| P3-T01 | `tools/validate.py`, `tools/manifest.py` | every batch, P5–P7 |
| P3-T02 | `tools/qa_take.py` | P4, P6 voice gates |
| P3-T03 | `tools/facts.py` | P5-T01, P7 overlays |
| P3-T04 | `tools/mix.py` | P4, P7-T03 |
| P3-T05 | `tools/build_composition.py` | P4, P7-T04 |
| P3-T06 | `tools/mux_final.py` | P4, P7-T05 |

## Exit criteria
- Each script passes its tests, and the tests are recorded in the task log.
- Running `--help` on each script prints its usage.
- No script prints more than 40 lines by default.
