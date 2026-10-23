# P6-T07 · Music (YuE 2)

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (+ optional human pick) | P5-T03 | YuE 2 (or fallback from MODELS.md) | 30–90 min | — |

**Goal:** the film's song, with music and vocals, built from the writer's lyrics, as in the post.

## Steps
1. Build `jobs/music.json` with 3 takes, `score_t1` to `score_t3`. Params:
   - `style`: `shot_list.music.style`;
   - `lyrics`: `script/lyrics.txt`, in YuE 2's section-tag format (as in P2-T11);
   - duration: `music.target_seconds`, if the tool takes one;
   - seeds 7001–7003.
2. Load YuE 2, generate the 3 takes, and download each to `audio/music/score_t1..t3.wav` (48 kHz stereo). If YuE 2 runs through a fallback, follow its P2-T11 recipe.
3. For each take, check with `ffprobe` that the duration is ≥ the film length. Optionally, transcribe with MOSS to confirm the vocals follow the lyrics roughly; one line each.
4. Pick the best take, by agent judgement or **[HUMAN]** if they want to listen. Copy it to `audio/music/score.wav` and set `music` in `edit/picks.json` to {`file`, `duration_s`, `source`, `mcp_seq`}.
5. Unload.

## Outputs
- `audio/music/score.wav`; `jobs/music.json`.

## Done when
- [ ] The score exists, is long enough, and is picked.

## STATUS line
`P6-T07 DONE · score_t2 picked (82 s, 48 kHz)` (example)
