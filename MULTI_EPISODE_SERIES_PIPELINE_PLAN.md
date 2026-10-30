# Multi-episode local series pipeline (branch `series`)

## Context

The repo produces single jobs: one brief + script → one video of 2-part segments (opening + continuations) via MiniMax H3 in ComfyUI. The owner wants a new branch that evolves this into a **multi-part series system**: recurring created characters, local-LLM-written short stories that span multiple episodes (minutes), fully local, with a delivered 3-episode sample arc (60–100 s per episode). Engine decision: keep MiniMax H3 (installed; native stereo audio; 9 reference-image slots `ref_images.ref_image_0..8` + `ref_audios` in local ComfyUI 0.38 `MiniMaxH3ReferenceToVideo`; proven 5–6 min per 124-frame segment). Per-character identity comes from locked master portraits + Ref2VA `<Subject>` conditioning; voices from Piper per-character voice models; scripts from Qwen3.5-9B GGUF on llama.cpp (CPU, no GPU contention). Closed-environment prototype: owner waived rights/license gating; record model+version used per asset in job folders so any future public release can still be reviewed. Do not touch the existing single-video form workflow.

Hardware: RTX 4060 Ti 16 GB, ~128 GB RAM, F: has hundreds of GB free. GPU may be held by the Strata engine (`strata.exe`); repo policy: stop Strata for media jobs (owner-authorized), rerun `nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader` before loads.

## Working agreement

- Branch off `main`: `git checkout -b series`. All work on this branch; do not merge without owner review.
- Update `STATUS.md` + `handoff.md` (repo rule) before GPU switches/session end; record outcomes in `MODELS.md`/`TOOLS.md` as the guide requires.
- Code style: mirror existing compact modules (`local_film/pipeline.py` one-liner density, `JobError` raises); tests: `unittest` in `tests/test_local_film_series_*.py` with `unittest.mock.patch` like `tests/test_local_film.py`.

## Step 1 — Data model and loading (`local_film/characters.py`, new)

Registry layout (create dirs on demand):

```
series/characters/<slug>/character.json, portrait.png, refs/*.png, audition-*.wav
series/<show-slug>/show.json, arc.md, cast.md
series/<show-slug>/episodes/<NN>-<slug>/episode.json, continuity.json
```

`local_film/characters.py` — functions `load_character(root, slug)`, `load_show(root, show)`, `load_episode(root, show, episode)` returning dicts after validation; raise `JobError` (import from pipeline; move nothing) on any violation:

- `character.json` required fields: `id` (== dir slug), `name`, `description` (≥20 chars, identity sentence), `appearance`, `voice_model` (filename inside `local-runtime/models/`), `voice_sample` (path under character dir, must exist), `portrait` (must exist), `ref_images` (≥2 relative paths, ≤9 total, all exist, portrait included first).
- `show.json` required: `id`, `title`, `logline`, `brief`, `style`, `width` (even, default 1280), `height` (even, default 720), `fps` (24), `characters` (≥1 existing slugs), `arc_summary`.
- `episode.json` required: `id`, `number` (int ≥1), `title`, `target_seconds` (30–300), `shots`: list of shot dicts with `id` (`shot-01`..`shot-99`, unique), `scene`, `action`, `continuation_action`, `prompt`, `characters` (≥1 slugs all in show cast), `speakers` (slugs subset of `characters`, may be empty), `dialogue` (list of `{character, text}`, `character` in `characters`; if empty, exactly one `{"character": "<first cast id>", "text": "<narration>"}`).

## Step 2 — Local writer (`local_film/writer.py` new, `tools/download_series_writer.py` new)

Copy the llama.cpp pattern from `local_film/planner.py` (spawn `local-runtime/llama/llama-server.exe` on a free port, `-ngl 0 -c 8192 --no-webui --parallel 1`, health poll, `response_format` json_schema, 2 correction retries on schema failure). Two functions, both pure-ish with logged JSON output next to the episode dir:

- `draft_script(show: dict, characters: dict[str, dict], arc_md: str, continuity_prev: dict, ep_brief: str, target_seconds: int, log_path) -> dict`
  Output schema (validate exactly, retry once): `{title: str, synopsis: str, lines: [{scene: str, setting: str, action: str, dialogue: [{character: <slug from cast>, text: str}]}], ending_state: str, next_hook: str}`. System prompt: show bible + full character descriptions + previous episode `ending_state` as authoritative continuity + "keep spoken words under ~2.7 words/second of target_seconds"; `lines` between 3 and 12.
- `storyboard(show, characters, script: dict, log_path) -> dict` → `episode.json` shots: for each script line emit one shot `shot-NN` (scene/setting from line; action; continuation_action = what happens after; prompt = setting + camera + per-present-character identity sentence from `character['description']` + `appearance` + action + style; characters; speakers+dialogue from line), plus copy `id/number/title/target_seconds/ending_state/next_hook` into `episode.json`.
- llama.cpp is CPU-only here (`-ngl 0`), safe to run while ComfyUI renders; never set `-ngl 99`.

Model: `tools/download_series_writer.py` — copy `tools/download_qwen35.py`'s download pattern (HF URL, `--force` refuse-overwrite, size sanity check) to fetch `unsloth/Qwen3.5-9B-GGUF` file `Qwen3.5-9B-UD-Q4_K_XL-0000x-of-0000x.gguf` split set — actually confirm the real filename first: read `tools/download_qwen35.py`, list the repo files via `https://huggingface.co/api/models/unsloth/Qwen3.5-9B-GGUF/tree/main` and download the `UD-Q4_K_XL` quant (multi-part: download all shards to `local-runtime/models/` and concatenate into `Qwen3.5-9B-UD-Q4_K_XL.gguf`). Env override `LOCAL_FILM_WRITER_MODEL` for model path (default that file).

## Step 3 — Character creation (`tools/create_character.py`, `tools/download_piper_voices.py`, both new)

`tools/download_piper_voices.py`: extend `tools/download_local_planner_voice.py`'s pattern to download listed voices from `https://huggingface.co/rhasspy/piper-voices` (`resolve/main/en/en_US/<name>/medium/en_US-<name>-medium.onnx` + `.onnx.json` into `local-runtime/models/`). Default list: `amy` (already present), `ryan`, `kristin`, `billy`, `raymond`, `zoey` (skip downloads for files that exist). If a name 404s, list the actual dir at `https://huggingface.co/api/datasets/rhasspy/piper-voices/tree/main/en/en_US/medium` and pick existing alternatives (same character slot names preserved in the printed table).

`tools/create_character.py` two modes:
- `--audition` : for each piper voice model present in `local-runtime/models/` synthesize the fixed sentence "The signal was clear tonight. I followed it to the door." with the same `piper.exe` invocation as `pipeline.voice()` into `series/characters/<slug>/audition-<voicename>.wav`, print the list, exit.
- `--create --name N --description D --appearance A --voice VOICENAME [--style S] [--portrait path]` :
  1. Portrait: if `--portrait` omitted, generate 3 candidates through Studio MCP exactly like repo evidence MCP sequences: `tools/studio_mcp.py call load_model` `{"kind":"image","model":"unsloth/FLUX.2-klein-4B"}` → `call generate_image` (3 seeds) → `unload_model`; write to `series/characters/<slug>/portrait-candidate-N.png`; owner approves by rerunning with `--portrait <chosen>`. Refuse to create without exactly one approved portrait file.
  2. Ref frames: generate a silent turning clip with the installed `tools/minimax_speech.py submit --name <slug>-orbit --image <portrait> --audio <local-runtime/silence-3s.wav> --frames 69 --allow-trailing-silence --prompt "The portrait subject slowly turns their head from profile to face the camera, then back, expression calm, identical clothing and framing, static camera."` (create `local-runtime/silence-3s.wav` once via ffmpeg `anullsrc`, mono 22050 Hz, matching Piper output; the LC node resamples — confirm the node accepts 22.05 kHz, otherwise resample the orbit audio to 44.1 kHz in the tool). Then `ffmpeg -vf fps=1 ... -vsync vfr` sample 4 frames to `refs/frame-0N.png`; keep portrait + best 3 as `ref_images` in character.json. If H3 render fails twice, fallback: `refs/` = the portrait cropped/zoomed square face region via ffmpeg `crop` — mark `ref_mode: "portrait-only"` in character.json and note the weaker conditioning in STATUS.
  3. Write `character.json` per Step 1 schema; validate with `characters.load_character`.
- GPU: before step 2 check `nvidia-smi` ≥12000 MiB free and stop nothing except reporting contention (stopping Strata is allowed per repo policy — say so in tool output).

## Step 4 — Pipeline series mode (`local_film/pipeline.py` + new `local_film/series.py`)

Extend, do not fork. All existing single-video behavior unchanged.

1. `validate(req)`: accept `req['kind']=='series'` with keys `show`, `episode`, `series_root` (default `series`), `width/height/fps/duration_seconds/segment_frames` etc. For series kind skip `brief/script/style` requirements and take them from show; keep all width/height parity checks.
2. New `local_film/series.py`:
   - `create_episode(series_root, show, episode, overrides={}) -> job dir` : builds `request.json` (`kind:'series'`, resolved absolute `show_path`, `episode_path`, `style`, `width`, `height`, `fps`, `duration_seconds` = episode `target_seconds` (0 = auto from narration minimum), seed_mode random, `segment_frames` default 124, `aspect` from width>height), then reuses existing `create()` internals to write job dirs under `JOBS` named `<YYYYmmdd-HHMMSS>-<uuid8>`.
   - `build_prompts(plan, show, characters) -> plan` : for each shot assemble the H3 full-reference prompt in the official six-section layout (see guide; sections `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`) with EXACT rules:
     * `ref_images.ref_image_0` = first present character's master portrait; slot numbering `ref_image_k` ↔ tag `<Picture k+1>`; one `<Subject i+1>` per present character defined as `is the <name> whose appearance comes from <Picture k+1>: <description> <appearance>`.
     * Show style sentence before `[Shot 1]`.
     * `retention_analysis`: every `<Subject i>: fully_preserved` with the traits list from description; `overall_soundscape`/`non_diegetic_music` default from show (minimal room tone / restrained strings bed strings in show.json optional fields with these defaults).
     * Continuation segments (index>0) keep existing continuation prompt behavior but retain subject definitions (`Continue seamlessly from the previous final frame. ... Keep <Subject 1> and clothing identical.`) — subject definitions ride every segment because ref conditioning is per-segment too.
     * `ref_images` slots beyond used characters are omitted; `ref_images.ref_image_size` = `match` (document `'max'` as the fidelity upgrade if owner rejects identity).
   - `voice_tracks(plan, characters, job, before, after)` replaces the piper section for series shots: per shot, run existing `pipeline.voice()`-style synthesis per dialogue line with `local-runtime/models/<character voice_model>` (same sha-guard + atomic rename pattern as `voice()`), concatenate line WAVs with 0.35 s silence gaps via ffmpeg concat filter, then apply existing `before/after` padding logic; store `shot['voice']`, `shot['voice_seconds']` exactly as today so `segment_schedule`/render need no change.
3. `pipeline.make_plan` branch: when `req.get('kind')=='series'` load `plan.json` = `episode.json` converted (shots already have planner fields) and skip the llama planner; `pipeline.voice` branches to `series.voice_tracks`; `pipeline.render_segment`: when shot carries `characters`, call `series.build_prompts` result instead of inline prompt strings and wire `graph['157']['inputs']['ref_images.ref_image_k']` from portraits (follow existing node-157 replacement block that already builds `MiniMaxH3ReferenceToVideo` + `SenseNovaH3DistilledBridge` + `graph['19']['inputs']['positive']=['160',0]`; copy that construction, extend the `inputs` dict loop — no new node classes; `ref_videos`/`ref_audios` stay unused this phase).
4. `wait_idle()`: series path requires ≥7000 MiB free (not 12000) after ComfyUI is idle, so the ~15 GB resident H3 stack (int8 model + convrot fp16 VAE + nvfp4 14.6 GB TE streaming) is not force-evicted mid-chain; comment the reason.
5. `pipeline.assemble()` unchanged (concatenation). New in series flow: title/end card — insert two 2.0 s generated-still segments per episode using the existing `assemble` machinery (images + `duration`): card 1 = `<show.title> — <episode.title>` over a 1-frame contact-sheet color from `series/<show>/cards/` (generate once via Studio image model, same call pattern as Step 3), card 2 = `Next time: <next_hook one line>`. Cards are built by `series.build_cards(plan, job)`.
6. Cross-episode continuity: after episode render completes, `series.save_continuity(job, episode_path, show_path, ending_state)` writes `continuity.json` into the episode dir: `{number, ending_state, next_hook, final_frame: <abs path extracted via existing extract_tail on assembled.mp4>, cast_refs: {char: portrait}}`. `series.create_episode` injects `continuity.json` of episode N-1 into the writer call (Step 2 `continuity_prev`); episode 1 gets `{}` (empty handling: no previous text).

## Step 5 — Entry points

- `tools/make_series.py`: `new-show --id --title --logline --brief --style [--characters n]` → writes `series/<id>/` skeleton + prompts writer once (`draft_arc`) to produce `arc.md` with 3 episode briefs (schema: `{episodes:[{number, brief, ending_note}]}`), `cast.md` naming 2 recurring characters + 1 per-episode; `new-episode --show --number --brief` (writer draft_script + storyboard → episode.json, prints owner-review path); `run --show --episode` → `series.create_episode` + enqueue onto the existing `FilmQueue` (import `local_film.queue`; no form-server needed).
- `local_film/server.py`: no change. Existing single-video workflow stays exactly as is.

## Step 6 — Sample arc production (the deliverable)

1. `tools/make_series.py new-show --id signal-in-the-snow ...` style brief: original story — "two radio operators at a polar listening post decode a signal that shouldn't exist; each episode ends further out on the ice, one character per episode gets closer to it." Two recurring leads (one per voice audition pick) + one rotating episode character. Landscape 1280x720, 24 fps.
2. Create 2–3 characters via `tools/create_character.py` (owner approves portraits + voices before renders — pause and report).
3. Draft + render 3 episodes (~50–60 narration seconds each + cards ≈ 60–75 s): each 3–4 shots → ~8–14 segments/episode, ~5–6 min/segment ⇒ 1.5–2.5 h GPU per episode; queue serializes (FilmQueue).
4. Per episode, produce contact sheets via `tools/contact_sheet.py` and record evidence paths in `STATUS.md`/`handoff.md`.

## Critical files & anchors

- `local_film/pipeline.py:260-366` — `render_segment` graph wiring (node ids 5/142/157/160/161/18/19/130/136); copy the node-160 block when extending refs; OOM-retry block must keep working.
- `local_film/planner.py` — llama.cpp spawn/health/json_schema pattern that `writer.py` must copy (and its 2-attempt correction loop).
- `comfy-local/ref2va-audio-comparison-graph.json` — base graph template loaded by `render_segment`; do not edit on disk (jobs copy semantics), read to confirm node ids before changing wiring.
- `local_film/queue.py` — enqueue/list/cancel used by `make_series.py run`; ACTIVE/TERMINAL sets must not change.
- `tools/download_local_planner_voice.py` + `tools/download_qwen35.py` — download patterns to mirror for piper voices + writer GGUF.

## Verification

Unit tests (fast, no GPU; run `python -m unittest discover tests -v` — same as existing suite):
1. `tests/test_local_film_series_prompts.py`: `build_prompts` with two characters → output contains `subject_definitions`, `<Subject 1>`/`<Subject 2>` bound to `<Picture 1>`/`<Picture 2>`, style sentence before `[Shot 1]`, and `graph['157']['inputs']['ref_images.ref_image_1']` wired for the second character (drive the actual `render_segment` patch-style test like existing `test_interrupted_submission_is_not_blindly_repeated`).
2. `tests/test_local_film_series_characters.py`: every `characters.py` validation error path (missing portrait, >9 refs, speaker not in shot `characters`, shot id collision).
3. `tests/test_local_film_series_schedule.py`: `duration_seconds=0` auto target = narration minimum + 0.25 s/shot; shot longer than 1 segment → correct part count with overlap 0.
4. `tests/test_local_film_series_cards.py`: episode of 3 shots → assembled segment list = 7 items in order `[card, s1, s2, s3, recap?, ...]` — exactly `[card1, ...shots..., card2]` — and `save_continuity` writes all keys (mock ffmpeg; reuse tmpdir + fake WAV fixture).
5. `tests/test_local_film_series_writer.py`: schema-violating writer output triggers exactly 2 corrections then failure; valid output round-trips to episode.json shot fields.

End-to-end (the real proof; needs owner portrait/voice picks and ~2 h GPU for episode 1):
6. Character: `tools/create_character.py --create --name ... --portrait <approved>` → `characters.load_character` passes; `refs/` has ≥2 images.
7. Episode: `tools/make_series.py new-episode --show signal-in-the-snow --number 1` → `episode.json` with 3–4 shots; owner edits; `run` → job completes → `review/assembled.mp4` ffprobes to 1280x720, 24 fps, AAC 48 kHz stereo, duration ≥ narration total; `review/quality.md` generated; contact sheet visually shows the same cast face across first and last shot (identity spot-check by owner).
8. Series span: episodes 2–3 render with episode 1 `ending_state` visible in episode 2's first shot scene text (grep `plan.json`) and card 2 of ep 1 contains ep 2 `next_hook` text from `continuity.json`.
9. Reuse: episode 2 request reuses identical portrait files and voice models without regeneration (`voice_text_hashes` guard passes on resume; segments of ep1 untouched on disk).

## Assumptions & contingencies

- Closed-environment prototype: owner waived model rights/license checks for this branch; still log model id + version per asset in job `settings.json`. If a future release target appears, rights review is required before publishing — recorded in STATUS at end.
- Identity quality: if the owner rejects character similarity, first try `ref_images.ref_image_size: 'max'` per episode (slower but best identity fidelity), then portrait-only `ref_mode` fix, then stop and report; do NOT start LoRA training (musubi-tuner H3/Wan video LoRA VRAM floor ≈24 GB vs this machine's 16 GB) as part of this plan.
- If Qwen3.5-9B UD-Q4_K_XL quant file names differ on the Hub, download whatever `UD-Q4_K_XL` variant exists (single file if present) — writer code only cares about the path.
- If Piper voice names 404, fall back to any 4+ distinct existing `en_US`/`en_GB` voices from the API listing (owner still auditions).
- If `LCH3AudioSync` rejects the 22.05 kHz silence fixture in the orbit render, resample the fixture to the node's expected rate (check node source `comfy-local/custom_nodes/ComfyUI_LC_AV_nodes/lc_h3_audio_sync.py`) — orbit is only reference material, audio content is irrelevant.
- `Lantern Keeper`-style show content above is the default creative brief; owner may replace premise/cast text before episode renders without touching code.
- If 4060 Ti VRAM pressure drops below H3 requirements because another process holds memory, stop Strata (`STATUS.md` records the owner authorization) — never stop ComfyUI or unrelated work.
