# P2-T14 · Render: HyperFrames test

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T07, P2-T04, P2-T11 | none (CPU) | 20–40 min | — |

**Goal:** render a 6-second 1080p composition built from real fixtures, measure render speed, and find out whether HyperFrames renders `<audio>`.

**Read first:** TOOLS.md › HyperFrames notes; `templates/composition_example.html`.

## Steps
1. Copy the fixtures into the render project:
   ```bash
   mkdir -p render/assets && cp tests/fixtures/motion_5b.mp4 render/assets/test_clip.mp4 && cp tests/fixtures/music_test.wav render/assets/test_music.wav
   ```
2. Write a 6 s composition at 1920×1080, following the HyperFrames notes, in the entry file the notes name:
   - the clip on track 0 (`object-fit: cover`);
   - the text "test" on track 1 from 1.0 s to 4.0 s;
   - **for this test only**, the music as an `<audio>` element on track 2.
3. Render with `RENDER_CMD` from TOOLS.md, inside `render/`. Time it, and send its output to `logs/tasks/P2-T14.out`. Copy the result to `tests/fixtures/render_test.mp4`.
4. Run `ffprobe` and record:
   - size (expect 1920×1080), duration (~6 s) and fps;
   - **whether the file has an audio stream**, in TOOLS.md › HyperFrames notes.

   Either way, the film is rendered silent and the audio is muxed afterwards.
5. Record render seconds per 10 s of film in MODELS.md › Render.

## Outputs
- `tests/fixtures/render_test.mp4`
- Render speed in MODELS.md

## Done when
- [ ] The MP4 is 1920×1080, about 6 s, and has the title text.
- [ ] Whether audio was rendered is recorded.

## If it fails
- **The video element shows black frames:** check how the HyperFrames notes say `<video>` should be declared (seekable media). The clip may need to be H.264 yuv420p; re-encode with ffmpeg if so.
- **The render is very slow (> 3 min per 10 s):** note it. The final 75 s render is a single overnight-safe step.

## STATUS line
`P2-T14 DONE · 6 s 1080p in 48 s; <audio> rendered: yes` (example)
