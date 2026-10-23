# P6-T08 · SFX + drone (MiDashengLM-Gen)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P5-T03 | MiDashengLM-Gen (or fallback from MODELS.md) | 45–90 min | — |

**Goal:** every sound cue in the script, plus the drone bed, at consistent levels, ready for the mix.

## Steps
1. Build `jobs/sfx.json` from `shot_list.sound_cues`: 2 variants per cue (`<x>_sfx_t1`, `_t2`), using each cue's `prompt` and `duration_s`. Drones are **15–20 s**, worded "seamless, slowly evolving, no melody", and looped in the mix. Keep within the model's 5–20 s range.
2. Load MiDashengLM-Gen, or use the P2-T12 fallback recipe. Generate each item to `audio/sfx/<id>_raw.wav`.
3. Convert each one to 48 kHz stereo and normalize its loudness:
   ```bash
   ffmpeg -hide_banner -loglevel error -nostats -y -i audio/sfx/<id>_raw.wav -af "loudnorm=I=-20:TP=-2:LRA=7" -ar 48000 -ac 2 -c:a pcm_s24le audio/sfx/<id>.wav
   ```
   Use `I=-24` for drones and ambience.
4. Pick per cue. If you can't judge by ear, prefer the variant whose duration is closest to `duration_s` and that has no clipping. Copy it to `audio/sfx/<x>_sfx.wav` and add it to `edit/picks.json` under `sfx.<x>`.
5. Unload.

## Outputs
- `audio/sfx/<x>_sfx.wav` for every cue; `jobs/sfx.json`.

## Done when
- [ ] Every cue has a picked file at 48 kHz and normalized.

## STATUS line
`P6-T08 DONE · 12 cues + 2 drones picked` (example)
