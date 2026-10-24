# P1-T01 · Install and start Unsloth Studio

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN (agent verifies) | P0-T04 | none | 15–45 min (first-run setup) | — |

**Goal:** Unsloth Studio runs locally, the owner account exists, and its memory settings follow the one-model-at-a-time rule.

## Steps
1. **[HUMAN]** Make sure Studio is current:
   ```powershell
   winget upgrade --id UnslothAI.Unsloth -e
   ```
2. **[HUMAN]** Start Studio, either from Start menu › Unsloth or with `unsloth studio` in a terminal. The first start finishes the setup, which can take a while.
3. **[HUMAN]** Create the owner account and password when asked.
4. **[HUMAN]** Open `http://127.0.0.1:8888`. If Studio uses a different URL or port, run `setx UNSLOTH_STUDIO_URL http://127.0.0.1:PORT` and tell the agent the URL.
5. **[HUMAN]** Settings › Resources:
   - **Keep model in GPU memory:** Off.
   - **Keep multiple models loaded:** Off.
   - **Allow oversized model loads:** Off.
   - **Idle auto-unload for image and video:** set to **60 seconds** (minimum), then Save. The UI says `0` keeps them loaded.
   - Leave **Don't reserve system RAM for the model** unchanged; this task only configures GPU model residency and unsafe oversized loads.
6. **AGENT** checks that Studio answers. It should print `200` or a 30x code:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8888/
   ```
7. **AGENT** writes the Studio URL (and the version, if the human reads it off Settings/About) into the TOOLS.md header.

## Outputs
- Studio running; URL and version recorded in TOOLS.md.

## Done when
- [ ] The Studio UI opens in the browser.
- [ ] The agent's `curl` gets 200 or 30x.
- [ ] The memory settings are as described in step 5.

## If it fails
- **The installer reports a GPU or CUDA problem:** update the NVIDIA driver, reboot, start Studio again.
- **The port is busy:** start Studio on another port (see `unsloth studio --help`) and set `UNSLOTH_STUDIO_URL`.

## STATUS line
`P1-T01 DONE · Studio 0.1.9xx at 127.0.0.1:8888, conservative memory settings` (example)
