ï»¿# Make a video on your PC

The pipeline creates a shot plan, generates a voice and video locally, joins the segments, and saves a review folder. You do not need to operate ComfyUI or move files between steps. The first run can take several minutes per video segment.

## 1. Open the form

1. On your current PC, open a browser and go to **http://127.0.0.1:8765**. The form may already be running.
2. If the page does not open, open `F:\film-pipeline` in File Explorer and double-click `Start-Local-Film.cmd`. A terminal opens and the browser form should appear. Keep the terminal open while using the form.
3. If the launcher says the address is already in use, close that extra terminal and try the address above. Do not start a second copy of the form.

On another PC, first follow `LOCAL_FILM_INSTALL_GUIDE.md`; copying just the launcher will not install the models or dependencies.

## 2. Describe the video

Fill in these fields:

- **Creative brief:** Describe the character, setting, mood and visible action. Example: `A woman in a green coat opens an old door, carrying a lantern. A mysterious transmission comes from the room beyond.`
- **Script:** Type the words you want the character to say. This becomes the narration. Separate different scenes with a blank line.
- **Visual style:** For example, `hand-drawn anime`, `cinematic live action`, `stylized 3D animation`, or `animated anthropomorphic fox`.
- **Character reference image paths:** Optional. Enter the full path to a local PNG, JPG or WebP image, one path per line. For example: `F:\film-pipeline\stills\reels\full-motion\01.png`. To get a path, right-click the image in File Explorer, choose **Copy as path**, paste it into the form, then remove the quotation marks. Leave the box empty to let the video model create a character.
- **Local music file path:** Optional. Enter the full path to an audio file already on your PC, without quotation marks. It is mixed quietly under the voice. Leave it empty for narration only; the form does not create music automatically.
- **Object reference:** Paste a local image path and describe the object, for example `F:\film-pipeline\stills\references\pny-rtx-5080.jpeg`. This is experimental; inspect the object and continuity in the result.
- **Speech silence:** The default is one second before and after each speech. Change either value to zero or another number of seconds. This adds to the duration needed for narration.
- **Width and height:** Leave **1080** and **1920** for Instagram Reels. Other even dimensions are accepted.
- **Frame rate:** Leave **24** unless you need 25 or 30.
- **Target seconds:** Leave **0** to fit the narration automatically. To request a longer video, enter a duration such as **10**. If that duration is too short for the generated narration, the job stops rather than cutting off the words; increase the duration in a new request.

The currently configured voice is a local US English voice named Amy. The form does not currently offer a voice selector.

## 3. Start or edit the plan

- For an unattended run, click **Start job**. Leave the form server running. You can leave the browser tab open and come back later; the status refreshes automatically.
- To inspect or change the plan first, click **Make editable plan only**. Wait until the status says `planned`, then click **Open plan editor**. Edit the shot descriptions or narration in the JSON, click **Save plan**, then click **Run / resume**. Keep the existing shot IDs such as `shot-01` and all required fields. Once generation begins, create a new job for narration changes.

The form shows a job ID and status. Select a job in the list to see its live worker and ComfyUI log, refreshed automatically. The ComfyUI log is shared and can include other local activity. `planning`, `voicing`, `waiting_for_gpu`, `rendering`, `assembling` and `checking` mean the job is working or waiting. Jobs run one at a time. The queue shows each waiting job and its position; Use **Cancel queued job** for a waiting job or **Cancel running job** for the active job. The status changes to cancelling while its worker and owned ComfyUI prompt stop; existing files remain in place. A cancellation can take time during a local processing step. The pipeline uses the final frame of a segment to start its continuation, so a longer clip can take several generation passes. Continuation prompts ask the model to move forward rather than repeat the opening action, but check the join: generative models can still repeat or change actions. Do not close the PC or put it to sleep during a run.

## 4. Find and review the result

When the status says **complete**, the pipeline attempts to open its review folder. If no window appears, open:

`F:\film-pipeline\local-film-jobs\YOUR-JOB-ID\review`

Replace `YOUR-JOB-ID` with the ID shown on the form. The folder contains:

- `assembled.mp4`: the finished video to watch.
- `segments`: the individual generated clips.
- `shot-plan.json` and `prompts.json`: the planned scenes and actual prompts.
- `settings.json` and `generation-state.json`: the request, settings and timing information.
- `quality.md` and `quality.json`: automated checks and warnings.
- `previews`: sampled contact sheets for the generated segments.

Play the entire video with sound. Check whether the character looks right, the mouth matches the speech, actions happen as requested, the voice is complete, and each continuation joins naturally. The automated checks can miss visual defects and cannot judge whether lip sync or music sounds good. They can also flag an intentional camera move as a possible continuity issue.

Every job gets its own folder. Previous videos and the older workflows remain available.

## 5. If a job stops

If the status is `failed`, read the error shown in the form and the job's `worker.log` and `review\quality.md` if present. A job with a recoverable failure can be restarted with **Run / resume**. If the form was closed, reopen it; the app will attempt to resume jobs that were active when it stopped. If you no longer have the original browser tab, you can resume a known job from a PowerShell window opened in `F:\film-pipeline`:

```powershell
python -m local_film.pipeline run "F:\film-pipeline\local-film-jobs\YOUR-JOB-ID"
```

If the error says the submission outcome is unknown, do not repeatedly restart the job: its ComfyUI history may have been lost, and a duplicate render is possible. Inspect the saved job and ComfyUI queue first. If the GPU is busy, wait for the other work to finish. For installation problems, missing models, port conflicts, backups or moving the project, use `LOCAL_FILM_INSTALL_GUIDE.md`.

## Current limitations

The pipeline has produced local test videos, but a new-machine installation was not tested. Character appearance and scene details can change unexpectedly, particularly between shots. The report flags some large changes but cannot catch every defect. Only the configured Amy voice is available through the current form; music must be supplied as a local file. The form and ComfyUI run on your PC, and model inference stays local.

## Instructions across segments

Use **Instructions for every segment** for rules such as "Camera stays static. No zoom, pan, tilt, or change of framing." The text is saved with the request, supplied to the planner, and appended unchanged to every video prompt, including reference-based segments and continuations. It takes precedence over conflicting planned descriptions. Keep one-time actions in the creative brief so they are not repeated. Prompt inclusion is verified by the pipeline; visual compliance still requires review. Existing jobs retain their saved prompts; use a new job for new instructions.

## Random or custom video seeds

Under the output settings, **Video seed** defaults to **Random for each new job**. The seed is chosen once at job creation and saved in `request.json`, job status, and review settings. Resume keeps it. Choose **Use my seed** to enter a whole number from 0 through 4294967295. This is the base seed; individual shots and continuations use consistent offsets. Reusing a seed needs matching prompts, references, models, settings, and runtime for comparable results. The planner can still produce different descriptions. Older jobs retain their original seed behavior.

## Reading live activity

Select a recent job to open **Live activity**. Choose **ComfyUI (shared)**, **Job worker**, or **Shot planner**. Warnings appear in amber and errors in red; use **Warnings & errors** to filter the recent output. **Follow latest** scrolls to new output; switch it off or scroll upward to read earlier messages. **Copy log** copies the current filtered view. Terminal escape codes and repeated progress updates are cleaned for display; original log files remain intact. The panel shows at most 200 recent lines per source. ComfyUI is shared, and its sampling percentage refers to a sampling pass rather than overall video completion. Full saved job data is under **Full job details**.

## Continuations with object references

The opening segment can use the supplied object reference through Ref2VA. Later segments use the previous final frame as an actual first-frame guide with the distilled image-to-video node and the same audio-sync method. The separate object/installation graphic is not fed into those continuations, which avoids reintroducing its original pose. This improves the grounding of the join, but does not guarantee physical action correctness: inspect that installed objects remain in place. Existing saved segment graphs are retained when resuming; create a new job or a reviewed replacement continuation to use the changed graph.

## Experimental motion overlap

A reviewed request can set `segment_frames` to 141 and `continuation_overlap_frames` to 22. This carries the previous 22 frames into the next segment with MiniMaxH3AddGuide, starts its speech track at the same overlapping time, and removes the repeated opening from both video and audio before assembly. The original default remains 124 frames without overlap. Raw generated segments remain in `segments`; trimmed continuation views are in `segments-aligned`. Settings, guide clips, original graphs, and review copies are saved. This mode is experimental until its actual output has been inspected; neither a valid graph nor an audio timing test establishes smooth visual motion.
