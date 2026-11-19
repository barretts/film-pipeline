# Last Train production notes

[Watch the four-shot cut](film/LastTrain-shots-1-4.mp4) · [Compare all fourteen photographic endpoints](film/keyframes.jpg) · [Open the animated Blender stage](LastTrain.blend) · [Read the seven beats](story.json)

## What actually ran

The train story has one visual question. Will Nell get her scarf back in time to board? The opening establishes ownership by showing her put it down to find her ticket. Ken notices it when she leaves. The intended payoff is Nell waving from inside the departing carriage with the scarf around her neck. The available 20-second cut ends when Ken raises the scarf. The handoff, boarding and farewell exist as Blender staging and endpoint photographs.

| Shots | Material saved |
| --- | --- |
| 1–4 | Two Blender guides and two photographic stills per shot, prompt, Wan job receipt, original video and 120-frame edit |
| 5–7 | Two Blender guides and two photographic stills per shot, prompt and submission marker. No accepted job ID or downloaded video is recorded locally. |

The four completed Wan jobs cost $0.30 each. OpenRouter returned HTTP 403 for the key's total spending limit during the remaining submissions. The reported $8.36 against an $8.00 cap was key-wide usage. The four train video receipts account for $1.20.

## Where the handwork went

1. I wrote seven five-second beats, chose the characters, and made the red scarf the single recognizable prop. I prompted a shared cast and station design photograph, saved as `design.png`.
2. I wrote `stage.py` for this story. I placed the actors, counter, doorway and carriage, chose seven camera angles, and keyed actor, train and scarf positions across 840 frames. The script embeds the story text as metadata. A change to that text alone does not change the acting. The actors are geometric proxies and the scarf follows authored coordinates. The photographic stage supplies hand poses, faces and cloth detail that the proxies do not encode.
3. Blender rendered frames 1/120, 121/240 and so on through 721/840 into `guides/`. For each endpoint I supplied its actual guide and the shared design photograph to image generation. I wrote a separate instruction for each frame specifying who held the scarf, where Nell was looking and whether she was outside or aboard. These one-off image calls happened in the assistant session. The saved PNGs preserve the results; the Python launcher does not recreate them.
4. The launcher fitted each still to 1280×720, built the contact sheet and sent Wan 3.0 two explicit endpoint images plus that shot's direction. It temporarily served those images over HTTPS, polled the jobs, downloaded the originals and conformed each result to five seconds at 24 fps. Each completed shot used its first video take. No alternate takes were selected.
5. I synthesized a continuous station ambience with rail rumble and chimes and saved the 35-second WAV. This story uses visual acting without spoken dialogue. After the spending limit interrupted the batch, I separately joined the four completed edits to the matching first 20 seconds of that track. The normal launcher assembles all seven when available.

## Reopening or resuming

The MP4, Blender file, keyframes and WAV can be opened directly. Run scripts from the repository root. Blender 5.2 can rebuild the scene and guide PNGs with `blender -b --python LastTrain/stage.py`; use a separate checkout if preserving the exact saved outputs matters. The video launcher uses the TakeFive Python runtime, Pillow, FFmpeg, cloudflared and the shared OpenRouter helper at `TakeFive/output/openrouter/seedance-mini-480p-one-pass/run.py`. That helper's KEYFILE points to the operator's external environment file. Configure it for the machine before running.

Before another paid run, check OpenRouter activity for shots 5–7. Each has a `submitted` marker and no local receipt. The launcher deliberately refuses a second submission with an existing marker. Recover a matching accepted job ID if one exists. Only clear a marker after confirming its request was rejected. With credit available, run `F:\TakeFive\runtime\inference-env\Scripts\python.exe -B -u LastTrain/render.py`. Existing edited clips are reused. Keep revisions in a new take directory because the current launcher skips existing edits by filename.

## Automation worth building next

- Start with a small shot manifest containing the story beat, cast IDs, camera, prop owner, starting and ending marks, and sound cue. For this story the scarf must move through Nell, counter, Ken and Nell again. Validate each cut against the preceding state before spending credits.
- Compile that manifest into a limited Blender vocabulary such as place, leave, notice, lift, transfer and board. Attach props to a hand or surface at named frames and test reach and visibility. Let the director edit the resulting stage when the handoff needs more care.
- Generate endpoint instructions from the same manifest, store the exact instructions, reference hashes, model and returned images, and show the fourteen stills together. Keep an approval point here. Check especially for a second scarf, a changed coat, or Nell appearing outside after boarding.
- Test the video model with one representative shot, then run a budgeted queue. Persist accepted IDs immediately, distinguish an explicit billing refusal from an uncertain network outcome, and key reuse to the input hashes. Assemble whatever has finished locally without contacting a provider.
- Evaluate story readability separately from file checks. A valid 120-frame clip can still obscure a transfer. Watch the cut without sound and ask when the viewer first knows whose scarf it is, who recovered it, and whether Nell made the train.

Snow-Direct is the earlier comparison production. It contains a more detailed hand-authored Blender performance and the completed seven-shot endpoint render. Its staging and soundtrack are separate from Last Train.
