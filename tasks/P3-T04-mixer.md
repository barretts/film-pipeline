# P3-T04 · Mixer: `tools/mix.py`

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (write 1 script) | P3-T01 | none (CPU) | 60–120 min | — |

**Goal:** turn the EDL's audio section into one mastered stereo file, with the music ducked under the voice and a loudness of −14 LUFS.

## Spec
- **Usage:** `mix.py --edl edit/edl.json --out mix/mix.wav --stems DIR [--target -14] [--tp -1.5] [--duck-db 10] [--json-out mix/loudness.json]`
- **`--stems DIR` is required.** It writes `voice.wav`, `music_ducked.wav`, `sfx.wav` and `drone.wav` (pre-master buses), and reports the ducking depth: the music bus RMS inside voice windows versus outside them, in dB.
- **Graph file:** build one FFmpeg filtergraph and write it to `mix/filter.txt`, so a long command line never breaks on Windows.
- **Per clip:**
  - `atrim` (in-point and length), then `aresample=48000` and `aformat=channel_layouts=stereo`;
  - `volume=<gain_db>dB`, plus `afade` in and out where given;
  - `adelay=<start_ms>:all=1`;
  - `apad=whole_dur=<duration_s>` so every input runs the full length. Drone clips with `loop: true` repeat; use `-stream_loop -1` on the input, or `aloop`.
- **Buses:**
  - voice = voice + dialogue;
  - music, sfx and drone are each their own bus;
  - ducking: `sidechaincompress` on music, keyed by the voice bus (starting point: threshold 0.03, ratio 8, attack 20 ms, release 400 ms). Tune it so music drops about `--duck-db` under speech.
  - master = `amix` of voice, ducked music, sfx and drone. Use `normalize=0` if the local FFmpeg supports it (`ffmpeg -h filter=amix`); otherwise make up the level with weights.
- **Loudness:** two-pass `loudnorm`:
  - pass 1 with `print_format=json`, then parse `measured_I`, `measured_TP`, `measured_LRA`, `measured_thresh` and `target_offset`;
  - pass 2 with `linear=true`.
- **FFmpeg version:** 7 or newer passes the graph file as `-/filter_complex mix/filter.txt`. Older versions use `-filter_complex_script mix/filter.txt`. Detect the version.
- **Output:** `pcm_s24le`, 48 kHz stereo, exactly `duration_s` long.
- **Report:** print integrated LUFS, TP, LRA, duration and clip counts, and write them to `--json-out`.

## Steps
1. Write the script.
2. Build `tests/samples/edl_audio.json`, 15 s, from the fixtures:
   - voice: `clone_t1.wav` at 2.0 s and `clone_t2.wav` at 8.0 s;
   - music: `music_test.wav` from 0, with `duck: true`;
   - sfx: `sfx_chalk_48k.wav` at 5.0 s;
   - drone: `drone_test_48k.wav` from 0 to 15, looped, at −18 dB.

   It needs only a minimal `video` entry to pass validation.
3. Run the mix:
   ```bash
   .venv/Scripts/python tools/mix.py --edl tests/samples/edl_audio.json --out tests/samples/mix.wav --stems tests/samples/stems --json-out tests/samples/loudness.json
   ```
4. Check:
   - −14 ±1 LUFS, TP ≤ −1.5 dBTP, and a length of 15.0 s;
   - **ducking:** the reported depth (from the stems) is **8–12 dB**.

## Outputs
- `tools/mix.py`; sample mix and report in `tests/samples/`.

## Done when
- [ ] The loudness targets are met.
- [ ] The ducking is measured at 8–12 dB.
- [ ] The length is exact.

## STATUS line
`P3-T04 DONE · −14.1 LUFS, TP −1.8, ducking 9 dB on sample` (example)
