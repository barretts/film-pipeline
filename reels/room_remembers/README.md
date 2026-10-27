# The Room Remembers - editable reels

Each episode is a separate 1080 x 1920 HyperFrames project with locally stored media. `episodes/` preserves the original painted-character drafts. `round-01/` through `round-04/` preserve the progressively revised three-style set; they are versions of the same stories, not twelve different stories. Finished videos are in `render/reels/round-XX/01.mp4`, `02.mp4`, and `03.mp4` under the repository root; the latest three are also copied to `render/reels/final/`. Files ending in `-master.mp4` and `-25fps.mp4` are render intermediates. No publishing service is involved.

From the repository root, rebuild the styled set after all matching source assets exist:

```powershell
& '.venv\Scripts\python.exe' reels\room_remembers\build_reels.py --variant styled --out-dir reels\room_remembers\round-01
```

By default the builder refuses to replace an existing episode. For a new round, copy `reels.json`, supply new captions with timings measured against that round's audio, update media paths, and use a new destination:

```powershell
Copy-Item reels\room_remembers\reels-round-04.json reels\room_remembers\reels-round-05.json
& '.venv\Scripts\python.exe' reels\room_remembers\build_reels.py --variant styled --profile readable_labels --spec reels\room_remembers\reels-round-05.json --out-dir reels\room_remembers\round-05
```

Each spec can override `talking`, `voice`, `broll`, `opener`, `portrait`, `music`, and `accent_path` with paths relative to the repository root; `opener_scale` controls its crop. `captions` contains `[start, end, text]` in seconds relative to the speech recording; `cut` uses the same clock. The builder shifts them by the 0.8-second opening and verifies the speech audio matches the lip-sync performance. Source talking videos are recompressed with one-second keyframes for reliable seeking. `readable_labels` uses larger captions and series labels. Apply the desired local HyperFrames media treatment after building, then check, preview, render at 30 fps, and review the exported file. `--overwrite` explicitly replaces generated episode files; preserve user edits before using it.

The exact media used in the first batch is stored locally in each episode's `assets/`. The narration and score were generated locally; model licenses and the user's desired publication context must be considered before sharing.
