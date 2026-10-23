# P2-T06 · Talking video: LTX-2.5 with native audio

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P2-T02 | LTX-2.5 | 30–90 min | — |

**Goal:**
- Make a talking clip in which LTX-2.5 generates the speech and the lip motion together.
- Find out what LTX-2.5 accepts: references, last frame, **audio input**, and maximum length.
- Get enough speech, ideally ≥ 6 s, for a test voice reference.

## Steps
1. Load LTX-2.5 (variant from MODELS.md).
2. Call `studio_status`, read the `generate_video` parameter list, and record LTX's capabilities in TOOLS.md › Capabilities:
   - references, last frame and size presets;
   - the **maximum frames**;
   - **whether it accepts an audio input**, and the parameter name.
3. Call `generate_video` with these settings. Use absolute paths (CONTEXT §8).
   - start frame `<ROOT>/tests/fixtures/portrait.png`;
   - 896×512, 24 fps, audio on, seed 4001;
   - frames: **241** (~10 s) if allowed, otherwise 121;
   - prompt:
     > The 2D hand-painted woman looks into the camera and says quietly, "Every feature arrives one at a time. I keep the lamp on so the machine can see me." Soft, low, slightly husky voice, close and intimate, quiet room tone, no music.
4. Wait for the job as CONTEXT §8 describes. Download it with `curl -fsS` to `tests/fixtures/talk_native.mp4`.
5. Check it with `ffprobe`: about 10 s (or 5 s) at 24 fps, **plus an audio stream**.
6. Extract the audio:
   ```bash
   ffmpeg -hide_banner -loglevel error -nostats -y -i tests/fixtures/talk_native.mp4 -vn -ac 2 -ar 48000 -c:a pcm_s24le tests/fixtures/talk_native.wav
   ```
7. Unload. Record minutes per clip, peak VRAM, and the frame count that worked in MODELS.md › Talking video.

## Outputs
- `tests/fixtures/talk_native.mp4` and `.wav`
- LTX capabilities in TOOLS.md, including audio input yes/no and max frames

## Done when
- [ ] The clip has both video and audio.
- [ ] The capabilities and the working frame count are recorded.

## If it fails
- **No audio stream:** find the audio on/off parameter in TOOLS.md and retry once.
- **OOM:** try 768×512, then 121 frames, then 97. Record what worked in MODELS.md › Production settings.
- **LTX-2.5 is unavailable in Studio:** use ComfyUI's LTX-2.5 workflow (fallback, ✋ for installing it). Record it in Decisions. These clips aren't MCP-logged.

## STATUS line
`P2-T06 DONE · 10 s talking clip w/ audio in 14 min; audio input: yes` (example)
