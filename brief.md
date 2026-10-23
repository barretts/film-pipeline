# Film brief (edit freely before P5)

**Subject:** a mysterious promo for **Unsloth Studio MCP**, made with Unsloth Studio MCP itself. (To make a different film, replace this line; the pipeline doesn't change.)

**Logline:** A quiet, hand-painted 2D woman shows us, one by one, what the machine in the dark room can do. Every feature she reveals is real and was used to make the film you are watching.

**Tone and style**
- Mysterious, slow-burn, A24-style: restrained, uneasy, beautiful. Long holds, slow push-ins, negative space.
- 2D hand-painted look: visible brush texture, muted palette (ink blue, bone white, rust, deep green), soft film grain, gentle vignette.
- One character, consistent across every shot. Every shot of her uses the master portrait as a reference.

**Structure (about 75 s)**
1. Cold open (≈10 s): darkness, drone, a single light. She speaks the first line.
2. Reveals (≈50 s): each feature revealed one at a time, as a shot and a title card. Order and wording come from the real MCP logs (script/features.json).
3. Classroom beat: chalk on a blackboard draws the **real loss curve** from the Qwen3-0.6B fine-tune.
4. Close (≈15 s): song swells, final line, title card showing the product name **from the logs** (`server.product`), cut to black.

**Sound:** low drone under everything; sparse, specific SFX (chalk, breath, room tone, a distant train); a song with vocals from YuE 2 built from the writer's lyrics. Narration in her voice, cloned with Breeze-TTS-2 from her own talking shots.

**Hard rules**
- Local models only, through Unsloth Studio MCP.
- Anything on screen that states a fact must come from the MCP call logs.
- Personal, non-commercial use only.

**Output:** 1920×1080, 24 fps, stereo 48 kHz, about 75 s, `render/final.mp4`.
