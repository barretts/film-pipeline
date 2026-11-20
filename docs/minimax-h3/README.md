# MiniMax H3 film workflow library

Collected November 19, 2026. For a new Blender-directed shot, start with the James-and-Kate baseline below. The other four entries are community examples for recurring sets, characters, sound, and portrait preparation. Their graphs have been collected where available. Their results on our 4060 Ti are untested.

## Directing a shot in Blender — locally reproduced

The successful James-and-Kate take used all 124 frames of the Blender guide in the native H3 reference-video input, separate Kate and James portraits, and a third still showing the finished radio room. The prompt assigned the orange and blue proxies to their actors. Sampling used 20 steps without turbo. At four matching checkpoints, the rendered room and actors replaced the gray set and capsules, with James close to the orange proxy’s horizontal position. The earlier 22-frame, four-step test retained the capsule. Several settings changed together, so the comparison establishes a working recipe rather than the contribution of any single setting.

[Working API submission](../../comfy-local/input/h3-creator-retest/james-submission.json) · [James and Kate](../../comfy-local/output/phase0/proper-james_00001_.mp4) · [Matching frames](../../comfy-local/output/phase0/proper-james-comparison.jpg) · [Creator’s importable ComfyUI graph](../../comfy-local/input/h3-creator-retest/workflow.json) · [Creator’s camera tutorial](https://www.reddit.com/r/StableDiffusion/comments/1wqydpg/blender_camera_motion_minimax_h3_ref2vid_in/) · [Multi-shot example](https://www.reddit.com/r/comfyui/comments/1xqm7ma/3d_blockout_to_ai_video_blender_minimaxh3_ref2vid/)

## Keeping a room recognizable across cuts

PATATAJEC photographed one office from 20 overlapping viewpoints and arranged them in a 4-by-5 grid within a 2048-pixel square. They created one RefMod from that sheet and also supplied larger photos for detail and for the prompted opening and closing views. They report that separate room references gave poorer continuity. They did not test the sheet alone as an ordinary reference. For a radio-room reverse angle, compare a single finished room still against a sheet of overlapping finished views, then try the RefMod. Keep the shot and seed fixed and check the door, window, desk, and radio.

[Reddit discussion](https://www.reddit.com/r/StableDiffusion/comments/1wwyva2/minimax_h3_refmod_consistent_location_trick/) · [Archived workflow PNG](workflows/location-workflow.png) · [Graph extracted from PNG](workflows/location-workflow.json) · [Author’s photos and RefMod](https://drive.google.com/drive/folders/1aMccjBDjp0uPPdGFzKXTT0SlRTIba6mB)

## Creating a reusable character RefMod

AlsterwasserHH separates creating the identity from generating a shot with it. The creation graph accepts character references including a voice sample. During generation, additional image, video, and audio inputs can be bypassed for a RefMod-only trial. The v2 revision fixes a resolution-selector issue by choosing dimensions divisible by 32. For James or Kate, test one identity across a change of angle before combining two identities in a scene.

The author’s transfer listed **MH3 Refmod train WF.json** and **MH3 Refmod WF v2.json**. The live host returned “Transfer unavailable” during collection. The Dainamo files below are separately attributed examples of the same two stages.

[Reddit guide](https://www.reddit.com/r/StableDiffusion/comments/1x4auud/minimax_h3_refmod_workflow/) · [Author’s transfer](https://getshared.com/d/K5cE7wHH) · [Tutorial cited by author](https://www.youtube.com/watch?v=2K6-OtV_Vbc)

## Visual, audio, motion, and style RefMods

Citadel_Employee’s tutorial links DainamoLabs’ separate creation and generation graphs. Use the creation graph to package references and the generation graph to apply them to a shot. For this project, the useful comparison is a recurring character or motion example versus the same source supplied directly. One commenter reported character duplication with two identities. Check whether James and Kate remain distinct at the desk before adopting this for two-person coverage. Spectrum is an optional acceleration node linked by the author.

[Reddit resource list](https://www.reddit.com/r/StableDiffusion/comments/1wvctmo/minimax_h3_refmods_video_audio_motion_style/) · [Video tutorial](https://youtu.be/blI0X5zslfw) · [Local creation graph](workflows/CreateRefMod.json) · [Local generation graph](workflows/GenerateRefMod.json) · [Upstream workflows](https://github.com/DainamoLabs/Workflows) · [RefMod nodes](https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod) · [Spectrum](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3)

## Stills and portraits — 20 MP image workflow

LilBrownBebeShoes provides text-to-image and image-edit branches. Enable the branch for the task. The posted recipe uses SamplerLCM, the simple scheduler, six steps, starting noise 1.10 and ending noise 0.90. Use text-to-image for new cast candidates and edit mode for variations of an approved portrait. The author reports artifacts at high magnification. Judge facial identity at the crop and resolution that will actually enter the video workflow. Local memory use and runtime remain unmeasured.

[Reddit guide](https://www.reddit.com/r/StableDiffusion/comments/1xt9ocv/minimax_h3_image_20mp_workflow/) · [Local portrait graph](workflows/Minimax-H3-Image-20MP.json) · [Author’s original images and workflow](https://huggingface.co/buckets/n8te0/diffusion/tree/Minimax-H3-Image-20MP)
