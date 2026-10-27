# Status

Updated 2026-10-27. `handoff.md` is the current resume point. Outcomes are not complete until their evidence is recorded and, where requested, reviewed.

| Outcome | State | Evidence / next step |
|---|---|---|
| Local baseline | In progress | Media works. Qwen 4B completed a bounded tool-using coding task and resumed context after unload/reload; a full film workflow remains unproven. |
| Replacement workflow | Done | Old task and phase plans replaced; root instructions and handoff updated. |
| Minimal pilot | Technical pilot rendered | `render/pilot.mp4`: generated SDXL still and Piper speech, four seconds, verified streams. Not a creative-quality pilot or full film. |
| Local lip sync | Working technical sample | MuseTalk produced `video/lipsync/v15/talking.mp4`; reusable `tools/lipsync.py` produced a second clip. Audio-delay control confirms animation follows the speech timing. |
| Preferred talking-shot workflow | Owner approved | MiniMax H3 speech-driven comparison was preferred over postprocessed lip sync. `tools/minimax_speech.py` is the default for new takes; see `TOOLS.md`. The approved comparison is a five-second shot, not a full reel. |
| Instagram reel batch | Three MiniMax reels ready for owner review | `render/reels/minimax/` contains moving anime, hand-drawn and 3D reels with narration, music and captions. Automated file and audio checks passed; actual sound balance and perceived lip sync need listening. The hand-drawn reel uses voiceover for its final profile section. See `handoff.md`. |
| Pilot review | Awaiting owner | Review `render/pilot.mp4`: room is brighter than the brief, square image is pillarboxed, and voice quality needs listening. |
| Reusable production pipeline | Not started | Extend the proven pilot path to another brief and production requirements. |
| Promo film and review | Not started | Produce the film from `brief.md`; obtain owner review of the final render. |

## Decisions

- The owner wants both the current film and a reusable pipeline. All inference is local; internet access is allowed for downloads, setup and research.
- Strata is optional and may be stopped to release GPU resources. Use a guided handoff if switching needs owner action.
- Keep the film brief with owner-approved creative substitutions when local feasibility requires them.
- Replace the old plans and handoff, including historical task documents; retain working code, generated artifacts and non-planning evidence.

## Evidence and current limitations

On 2026-10-26, after the Strata engine was stopped with the owner's authorization, the preflight measured 16,380 MiB total GPU memory, 976 MiB used and 15,134 MiB free; Studio health passed and F: had 531,816,910,848 bytes free. These are point-in-time readings, not current capacity guarantees. The existing MCP logger, contact-sheet utility, schemas and starter render exist; the production model choices and end-to-end media pipeline are not yet proven. Verify all state again before acting on it.

Direct local MCP calls were verified and captured; Piper generated `audio/pilot/piper-smoke.wav` (2.74 seconds, mono 22.05 kHz). SDXL generated `stills/pilot/sdxl-smoke.png` (512x512); Lumina generation failed HTTP 500. The assembler produced `render/pilot.mp4` from those local assets, and ffprobe confirmed four seconds, H.264 1920x1080 at 24 fps, and AAC stereo 48 kHz. A frame was inspected; audio contains a non-silent signal but has not been auditioned. The voice's rights for the final promo remain unresolved. SDXL terms were reviewed in `MODELS.md`. A small local Qwen model correctly answered a simple coding prompt, but agent tool use and session resume are not yet tested. Six automated tests passed, including three assembly tests using synthetic media. The film and reusable production workflow are unfinished.

On a fresh rerun, Studio generated new SDXL and Piper assets (MCP sequences 38–43), then `tools/assemble_pilot.py` produced `render/verify_f5d1cdf1.mp4` using `edit/verify_f5d1cdf1.json`. FFprobe confirmed four seconds, 1920x1080 H.264/24 fps, and 48 kHz stereo AAC; FFmpeg decoded both streams successfully and detected non-silent audio. The result was not auditioned. This sequence was manually orchestrated; it does not establish an automatic end-to-end film pipeline.

An isolated local OMP agent using Qwen 0.8B invoked tools but did not complete a simple coding task: it repeatedly called write without required content and failed to create the requested file despite exit code 0. A separate resume check recovered the prior marker from the saved session. Evidence: `logs/local-agent-smoke/sessions/2026-10-27T04-52-37-432Z_01a17bb4-03b8-75f7-b722-509faf24964d.jsonl`. The model was unloaded afterward. Do not use the exit code alone as task verification.

The stronger Qwen3.5 4B UD-Q4_K_XL model completed a bounded OMP coding task, using two reads and one write; four independent cases passed and the requirements file remained unchanged. After unloading and reloading the model, its saved session recovered the earlier marker. The prompt specified the write-tool schema and retry rule; this does not prove unattended film production. The video playback issue was traced to private temporary-directory permissions, corrected for existing renders and fixed in the assembler; an ACL regression test passes.

Stable Audio 3 Small Music produced `audio/pilot/stable-audio-music-smoke.wav` locally (MCP sequences 71–73): eight seconds, 44.1 kHz stereo, non-silent. YuE2 produced lyric-conditioned `audio/pilot/yue2-vocal-smoke.wav` (seq 74–77), non-silent 69.639 seconds, 48 kHz stereo. Studio warned it ignored both the requested eight-second duration and `semantic_max_tokens`. Neither output has been auditioned; audible vocals and quality remain unverified. Studio's audio-reference interface does not establish speech-driven lip synchronization, so the successful test below used MuseTalk locally.

On 2026-10-27, local MuseTalk 1.5 generated the talking portrait from `stills/lipsync/character.png` and `audio/lipsync/character.wav`. A one-second speech delay shifted the closest matching mouth frames by 25 frames at 25 fps; this tests audio-driven timing but not subjective phoneme accuracy. The reusable command rendered `video/lipsync/space test/speaking sample.mp4`, using input and output paths with spaces; its decoded audio had correlation 0.99978 with the supplied speech and the file inherited user-readable Windows permissions. The technical voice's final-promo rights remain unresolved.

The Room Remembers batch contains three original fictional stories, each rendered four times as successive revisions: `render/reels/round-01/` through `round-04/`. Latest copies are `render/reels/final/01-anime.mp4`, `02-hand-drawn.mp4` and `03-3d-animated.mp4`. All 12 intended exports were checked for 1080x1920 H.264 at 30 fps, stereo AAC, full decode, readable Windows ACL, visible changes and matching narration. Phone-sized frames were inspected; speech/music were measured and transcribed but not auditioned. The 2D lip-sync mouth retains some realistic softness. The generated score's terms should be reviewed for any actual publication.
