# Full-motion reel assembly

For new talking shots, use the owner's preferred speech-driven MiniMax H3 workflow documented in [TOOLS.md](../../TOOLS.md#preferred-speech-driven-minimax-shots). It generates the character's movement conditioned on the recorded narration; the older LatentSync mouth-replacement path remains a fallback. Review the shots and their audio before assembly.

This creates a new editable HyperFrames project for each reel. It needs a **finished, visually reviewed talking video** long enough for the complete paced narration, with that exact narration in its audio starting at time zero. The current 4.56-second WAN shots are not long enough and cannot be passed off as finished talking videos. There is no still opening, still B-roll, loop, or frozen tail in this assembly.

From `F:\film-pipeline`, for example:

```powershell
.\.venv\Scripts\python.exe reels\full_motion\build.py --id 03 --video video\full_motion\prepared-03.mp4 --out reels\full_motion\projects\03
```

Replace the example input with the real prepared video. Choose `01`, `02`, or `03` for the existing paced narration and its corresponding caption timings. The target directory must not already exist. The builder copies media into the new project; it does not edit the old reels or overwrite the original sources. It uses the existing ambient music and paced voice, and places the moving video, voice, music, and captions on separate editable tracks. The footage's own matching narration is muted in the composition to avoid doubling the voice.

The gate verifies a decodable near-9:16 video, video and decoded audio coverage, audio correlation with the selected narration, and localized pixel changes outside a face exclusion in overlapping two-second windows. Specify a box if the default does not cover the face throughout the video, for example `--face-box 0.2,0.1,0.5,0.3` (normalized x,y,width,height). `input-review.json` records the measurements. These checks are conservative: natural low-motion performance may be rejected, and lighting changes, backgrounds, camera zoom, cuts, or distortion can be mistaken for motion. **A pass does not establish natural body movement, identity, continuity, lip sync, or artistic quality.** Watch the entire prepared video, including any joined-shot seams, before building and watch the rendered reel afterward.

Open the project in the HyperFrames desktop app or preview it locally. To check and export, run these commands inside the new project:

```powershell
npm run check -- --json
npx --yes hyperframes@0.8.188 snapshot --review
npx --yes hyperframes@0.8.188 render --fps 30 --quality delivery --output renders\reel.mp4
```

The project is 1080×1920. A source near 9:16, including the WAN 704×1280 portrait format, is scaled to fill with a small crop; the export is explicitly 30 fps. Source inference at 16 fps does not become 30 distinct generated frames. Review on a phone-sized preview and verify the resulting file's dimensions, frame rate, duration, audio and visual quality before delivery.
