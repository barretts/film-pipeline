# Local suspense cues

The first reel batch uses separate 48 kHz WAV stems so music and effects can be balanced against the narration. `ambient.wav` is the previously generated Stable Audio 3 Small Music sample (`audio/pilot/stable-audio-music-smoke.wav`) joined to itself with a 1.2-second crossfade. Its duration is 14.8 seconds. The Stable Audio model's applicable license conditions remain relevant.

`heartbeat.wav` (1.20 s), `door.wav` (1.15 s) and `chime.wav` (1.20 s) are deterministic, locally synthesized accents created by `make_cues.py`; they do not use external audio recordings. They evoke a double heartbeat, a wooden hinge, and a quiet glass strike. These are designed effects, not recordings of real objects.

For the roughly 12-second reels, start the music at 0 seconds with gain 0.12, a 0.6-second fade in and a 0.8-second fade out. Place heartbeat around 6.3 seconds in reel 1, door around 4.0 seconds in reel 2 and chime around 5.5 seconds in reel 3, adjusting to the actual edit. Start each effect at gain 0.20. At these settings the music's measured RMS is about 12 dB below the current narration; listening and final loudness checks are still needed.

To regenerate, move or rename the four existing WAV outputs first, then run `& '.venv\Scripts\python.exe' audio\reels\sfx\make_cues.py` from the project root. The script refuses to overwrite them. The script needs NumPy, SciPy, SoundFile, FFmpeg, and the existing Stable Audio source sample.
