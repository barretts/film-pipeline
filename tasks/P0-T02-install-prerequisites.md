# P0-T02 · Install prerequisites

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN | P0-T01 | none | 20–40 min | — |

**Goal:** Git, Node.js 22+, FFmpeg, Python 3.12, Unsloth (Studio + CLI) and Claude Code are installed and on PATH.

## Steps
1. **[HUMAN · PowerShell]** Run:
   ```powershell
   winget install --id Git.Git -e
   winget install --id OpenJS.NodeJS.LTS -e
   winget install --id Gyan.FFmpeg -e
   winget install --id Python.Python.3.12 -e
   winget install --id UnslothAI.Unsloth -e
   irm https://claude.ai/install.ps1 | iex
   ```
2. Open a **new** PowerShell window, so PATH refreshes, and check:
   ```powershell
   git --version; node --version; (ffmpeg -version)[0]; py -3.12 --version; claude --version; Get-Command unsloth
   winget list --id UnslothAI.Unsloth
   ```
   - Node must be **v22 or newer**, which HyperFrames needs.
   - Unsloth must be **0.1.909-beta or newer**, which adds `unsloth mcp add`. If it's older: `winget upgrade --id UnslothAI.Unsloth -e`
3. Run `claude` once and complete the sign-in.
4. Run the checker again (P0-T01 command). No tool-related `[FIX]` lines should remain.

## Outputs
- All tools above work from a new terminal.

## Done when
- [ ] The step 2 commands all print versions, and Node is ≥ 22.
- [ ] Claude Code is signed in.
- [ ] The checker shows no `[FIX]` lines for git, node, ffmpeg, claude or unsloth.

## If it fails
- **`winget` is missing:** install "App Installer" from the Microsoft Store.
- **A command isn't found right after installing:** open a new terminal. Still missing? Re-run that `winget install … --force`.
- **`claude` isn't found:** see the "Fix your PATH" section of https://code.claude.com/docs/en/quickstart
- **The Unsloth installer needs extra components (CUDA/PyTorch):** let it finish; first setup can take a while.

## STATUS line
`P0-T02 DONE · all tools installed; node v24, unsloth 0.1.909` (example)
