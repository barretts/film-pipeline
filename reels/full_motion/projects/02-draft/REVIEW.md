# Experimental draft review

This draft uses the reviewed hand-drawn WAN shot and continuation, DWPose-based LatentSync, the 02 narration, the local ambient bed and captions. Its source remains in `jobs/handdrawn-dwpose-latentsync.mp4`; the original joined motion remains in `video/full_motion/handdrawn-joined-retry.mp4`. The source motion was generated at 16 fps and converted for lip sync and export, so the 30 fps export does not contain 30 unique generated frames per second.

The assembly gate passed. HyperFrames check reported no errors or warnings. The H.264/AAC MP4 is 1080×1920, 30 fps and 8.033 seconds; a complete video and audio decode passed. Phone-sized decoded frames in `renders/phone-render-review.jpg` show legible captions, a moving arm and lantern. They also show an imperfect hand and changes in coat and torso shape. The final mix measured −25.7 dB mean and −8.4 dB peak; it was measured, not heard. Lip phonemes and naturalness still require a human watch and listen.

The lip-sync experiment used DWPose anchors and did not load the non-commercial InsightFace `buffalo_l` weights. This does not clear the other model and media terms: `tools/LATENTSYNC.md` inventories them, including the Stable Audio Community License and Gemma terms for the ambient bed. This is an experimental draft, not a polished final or legal clearance.
