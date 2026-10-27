# Draft review

The 03 draft uses the reviewed moving mirror shot and its continuation, the matching local narration, ambient music and timed captions. The source is 704×1280; the draft is composed and exported at 1080×1920, 30 fps. The source footage remains separate and editable in the project.

HyperFrames check returned no errors or warnings. The input gate decoded the speech and video, measured narration correlation of 0.99994 and detected localized non-face pixel changes across the narration. The final MP4 decoded completely and reports 253 video frames with a 48 kHz stereo AAC stream. FFmpeg measured average audio level −25.6 dB and peak −4.7 dB; the mix was measured, not heard. A software-rendered phone sheet and a sheet made from decoded output frames were inspected: captions were legible at 360 px wide and the character's hands and upper body visibly change position. These checks do not prove natural movement or accurate phonemes.

The weakest section is the continuation: the hand raises rather abruptly and some fingers look imperfect. More natural movement and hand anatomy would need another generation. The final 40 ms source frame has its original mouth rather than a generated mouth, so the full narration can be retained without freezing the video. The detector weights are available for non-commercial research only. The final mix and the lip synchronization still require a human listen and full-speed viewing.

Phone review: `renders/phone-render-review.jpg`. Face comparison and chunk-boundary stills are in `jobs/mirror-latentsync-faces.jpg` at the project root. The original moving source is `video/full_motion/mirror-joined.mp4`; the prepared full-speech input is `jobs/mirror-latentsync-full-speech.mp4`.
