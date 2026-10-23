# P2-T12 · SFX + drone: MiDashengLM-Gen

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T04, P1-T06 | MiDashengLM-Gen | 20–60 min | — |

**Goal:** generate one specific sound effect and one drone bed, and confirm they can be used once resampled.

## Steps
1. Check MODELS.md. If MiDashengLM-Gen is in the catalog (it would appear on Studio's Music › SFX page), load it and call `generate_audio` in its sfx/music mode twice:
   - "chalk scratching on a blackboard in an empty classroom, close, dry, no music", 5 s → `tests/fixtures/sfx_chalk.wav`
   - "low sub-bass drone with distant wind, slowly evolving, no melody", 20 s → `tests/fixtures/drone_test.wav`
2. Resample both files to 48 kHz stereo (§10), saving as `*_48k.wav`.
3. Record seconds per cue in MODELS.md › SFX. Unload.

## Outputs
- `tests/fixtures/sfx_chalk_48k.wav`, `drone_test_48k.wav`

## Done when
- [ ] Both sounds exist at 48 kHz and match their prompts closely enough to use.

## If it fails (not in Studio)
Use the official repo in its own venv.
1. Unload all GPU models first.
2. Create the venv and install CUDA PyTorch, choosing the newest CUDA wheel that the driver supports (nvidia-smi shows the maximum CUDA version):
   ```bash
   py -3.12 -m venv venvs/midasheng
   venvs/midasheng/Scripts/python -m pip install -q torch torchaudio --index-url https://download.pytorch.org/whl/cu128
   venvs/midasheng/Scripts/python -m pip install -q transformers accelerate soundfile
   ```
3. **[HUMAN]** The model loads with `trust_remote_code`. Skim the Python files on its Hugging Face page (`mispeech/midashenglm-gen`) and approve before running.
4. Write `tools/sfx_midasheng.py`, following the usage example on the model card. It takes a prompt and duration and writes a 16 kHz WAV. Generate both cues, then do step 2.
5. Record "SFX via repo venv" in Decisions. SFX carry no on-screen facts.

If that path is also blocked, use **Stable-Audio-3-Medium-GGUF** from the Studio catalog (Music page). It is personal use only under its community license. Record it.

## STATUS line
`P2-T12 DONE · chalk + drone OK after 48 kHz resample; 9 s/cue` (example)
