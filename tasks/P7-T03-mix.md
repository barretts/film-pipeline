# P7-T03 · Mix

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ optional human listen) | P7-T02 | none (CPU) | 15–45 min | — |

**Goal:** the film's master audio, `mix/mix.wav`: −14 LUFS, true peak ≤ −1.5 dBTP, with the music ducked under her voice.

## Steps
1. Run the mixer:
   ```bash
   .venv/Scripts/python tools/mix.py --edl edit/edl.json --out mix/mix.wav --stems mix/stems --json-out mix/loudness.json
   ```
2. Check that:
   - the integrated loudness is −14 ±1 LUFS;
   - TP ≤ −1.5 dBTP;
   - the duration equals the EDL's `duration_s` to within 0.05 s.
3. Check the ducking depth that the mixer reports from `mix/stems`. It must be 8–12 dB.
4. Optional **[HUMAN]**: listen to `mix/mix.wav`. Gain changes go into the EDL (`gain_db`); never hand-edit the WAV. Then re-run step 1.

## Outputs
- `mix/mix.wav`, `mix/loudness.json`.

## Done when
- [ ] The step 2 loudness and duration targets are met.
- [ ] The ducking is in range.

## STATUS line
`P7-T03 DONE · −14.0 LUFS, TP −1.7, 76.4 s` (example)
