# Signal in the Snow — Three Taps

[Watch Draft A](Three%20Taps.mp4) · [Shot order and sound cues](sequence.json) · [Radio mix](radio-mix.wav)

The desk crossing is the approved proper-james take. The pickup and snowy exterior were generated locally for this cut using the MiniMax H3 reference model, 20 sampling steps and still references. Their saved submissions identify the input files, model settings and output paths. The receiver, listening two-shot, latch, waiting shot and transmission use existing project footage. The four lines were recorded with local Piper voices and placed against the picture edit. The final taps play over black. The episode ends before Kate goes outside.

## Edit

| Time | Picture and sound |
| --- | --- |
| 0:00–0:03 | Three taps from the receiver. |
| 0:03–0:08.17 | James crosses to Kate at the radio desk. |
| 0:08.17–0:12.17 | They listen. Three more taps, then a voice asks for the door. |
| 0:12.17–0:17.17 | James takes the walkie and tells Kate to stay on the set. |
| 0:17.17–0:20.17 | He opens the outer door. |
| 0:20.17–0:25.17 | Through the window, James radios back and walks out of view. |
| 0:25.17–0:27.67 | Kate waits. |
| 0:27.67–0:31.67 | Kate asks James to come back inside. |
| 0:31.67–0:33.67 | Black. Three taps. |

From the repository root, run the following to assemble the pictures with the saved performances and mix. Running the script without the flag resynthesizes the four lines. The edit uses FFmpeg, ffprobe, Python, NumPy and SciPy.

```powershell
python TakeFive/films/signal-in-the-snow/draft-a/build_cut.py --picture-only
```

[Walkie submission](pickup-job.json) · [Exterior submission](outside-job.json) · [Episode script](../../../../series/signal-in-the-snow/episodes/01-signal-in-the-snow-episode-1/episode.json)
