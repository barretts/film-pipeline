# P0-T04 · Project folder, venv, git

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT (first agent task) | P0-T03 | none | 15–30 min | — |

**Goal:** the project lives on the model drive, has a Python venv with the helper libraries, the working folders exist, and git tracks the text files.

**Before you start:**
- **[HUMAN]** Copy this whole package folder to the model drive, e.g. `X:\film-pipeline`. Keep the path short.
- Open a terminal in that folder and run `claude`. The agent takes over from here.

## Steps
1. Read the P0-T01 verdict (one-liner in P0-T01 step 4) and log it.
2. Create the venv and install the libraries:
   ```bash
   py -3.12 -m venv .venv
   .venv/Scripts/python -m pip install -q --upgrade pip
   .venv/Scripts/python -m pip install -q -r tools/requirements.txt
   .venv/Scripts/python -c "import numpy, soundfile, librosa, PIL, jsonschema; print('imports ok')"
   ```
3. Create the working folders. Don't create `render/` here; HyperFrames creates it in P1-T07.
   ```bash
   mkdir -p logs/tasks logs/sheets tests/fixtures tests/samples jobs script stills/candidates \
            video/motion video/hero video/talking video/candidates \
            audio/ref audio/vo audio/dialogue audio/music audio/sfx captions train edit mix
   ```
4. Set up git (local only):
   ```bash
   git init
   cp templates/gitignore.txt .gitignore
   git config user.name "film-pipeline"; git config user.email "film@localhost"
   git add -A && git commit -m "P0-T04: project scaffold"
   ```
5. Fill in the STATUS.md header: project root path and model drive.

## Outputs
- `.venv/`, the working folders, `.gitignore`, and the first commit.

## Done when
- [ ] `imports ok` printed.
- [ ] The folders exist.
- [ ] `git log --oneline | head -1` shows the scaffold commit.

## If it fails
- **librosa or numba won't install on 3.12:** upgrade pip, then retry with `--only-binary=:all:`. Last resort: install Python 3.11 (`winget install --id Python.Python.3.11 -e`) and rebuild the venv with `py -3.11`.
- **`py` isn't found:** use the full path of Python 3.12, or `python`. Note this; P1-T03 depends on it.

## STATUS line
`P0-T04 DONE · venv ok, folders + git at X:\film-pipeline` (example)
