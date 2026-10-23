# P1-T06 · Map models to the catalog → MODELS.md

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P1-T05 | none (downloads only) | 30 min + downloads (hours) | — |

**Goal:** every personal-lane role has an exact model id and variant, or a named fallback, and the big downloads are under way.

**Read first:** MODELS.md; CONTEXT §4; TOOLS.md (`list_models`, `load_model`).

## Steps
1. For each workflow (image, video, speech/clone, music/sfx, separate, transcribe), call `list_models(source="catalog")` **with the workflow filter** from TOOLS.md. Never request the unfiltered catalog; it is ~130 rows.
2. For each MODELS.md row, find the matching catalog row. Record:
   - the id and variant;
   - the size in GB (`size_bytes`/1e9);
   - `fits_now`;
   - `low_vram`.

   Matching rules for the trickier roles:
   - **Wan2.2-TI2V-5B:** use the GGUF (`low_vram`) row, not the 24 GB safetensors row.
   - **Wan2.2-I2V-A14B:** use the GGUF expert pair, Q5_K_M if it's listed.
   - **LTX-2.5:** pick the variant the catalog marks as fitting this GPU.
   - **LLMs** (writer and fine-tune base) aren't in the catalog. Use the HF ids `unsloth/Qwen3.8-27B-GGUF` (variants `UD-Q4_K_XL` and `UD-Q3_K_XL`) and `unsloth/Qwen3-0.6B`.
3. If a role has no catalog row, write `NOT IN CATALOG → fallback: <name from MODELS.md>`.
4. Start the downloads, biggest first: A14B, LTX-2.5, Qwen3.8-27B, Wan2.2-5B, YuE 2.
   - Use the download-ahead or preview option from TOOLS.md if it exists. Otherwise let `load_model` download the model, then unload it.
   - After each download, check free space:
     ```bash
     df -h /x
     ```
     (Use the model drive letter in lowercase.) **Stop if less than 30 GB would remain.**
5. Fill in "Total downloaded" and "Free space left".

## Outputs
- MODELS.md id/size/fits columns filled in; downloads started or done.

## Done when
- [ ] Every row has an id or a named fallback.
- [ ] The five big models have been downloaded or are downloading.
- [ ] The free-space check is recorded.

## If it fails
- **A download stalls:** Studio retries XET downloads over HTTP. If it still fails, see Unsloth's "Hugging Face Hub, XET debugging" doc page and retry later.
- **A model needs a Hugging Face license click-through:** ask the human to accept it on the model page (✋ rule §3.7).

## STATUS line
`P1-T06 DONE · 11/12 roles in catalog; MiDashengLM-Gen → repo fallback; 160 GB downloaded` (example)
