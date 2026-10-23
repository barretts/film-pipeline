# P2-T11 · Music: YuE 2

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T04, P1-T06 | YuE 2 (YuE2-3B) | 20–60 min | — |

**Goal:** generate a short song with vocals from lyrics and a style prompt, and measure it.

## Steps
1. Check MODELS.md for a catalog row for YuE 2.
   - If there is one: load it.
   - If there isn't: go to **If it fails**.
2. Write 8 short lyric lines of your own, in two sections, into `tests/fixtures/music_test_lyrics.txt`. Use the section-tag format from YuE 2's example lyrics file (the `examples/*.json` on its model card).
3. Call `generate_audio` in **music** mode with model YuE 2 and those lyrics, asking for a link. If the tool takes a duration, ask for about 30–40 s. Style:
   > dark ambient folk, intimate female vocal, sparse felt piano, cello drone, 70 bpm, minor key
4. Download to `tests/fixtures/music_test.wav`. `ffprobe` should show 48 kHz stereo; note the duration.
5. Optional: transcribe it with MOSS and note roughly whether the vocals follow the lyrics.
6. Unload. Record minutes per song and peak VRAM in MODELS.md › Music.

## Outputs
- `tests/fixtures/music_test.wav`, `music_test_lyrics.txt`

## Done when
- [ ] A song with vocals exists, and its format and time are recorded.

## If it fails
YuE 2 isn't in Studio, or it fails on Windows. Try these in order, and record which one you used in Decisions:
1. **YuE2-Studio**, the community Windows app. It needs ✋ approval as community software. **[HUMAN]** installs it and generates with the same style and lyrics, then saves to `tests/fixtures/music_test.wav`.
2. **yue2.cpp** with GGUF `botp/YuE2-GGUF` (✋ approval), run by the agent from a separate folder.
3. **WSL2 Ubuntu** with the official `yue2_infer` package.

Music carries no on-screen facts, so outputs from outside MCP are acceptable.

## STATUS line
`P2-T11 DONE · 36 s song, 48 kHz stereo, 2.6 min, peak 11.4 GB` (example)
