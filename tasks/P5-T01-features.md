# P5-T01 · Feature list from the real logs

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| AGENT | P4-T04 | none | 20–30 min | — |

**Goal:** decide which real Unsloth Studio MCP features the film reveals and in what order. Every title must trace back to logged calls.

**Read first:** TOOLS.md (one-line tool descriptions); P5 phase file (truth rule).

## Steps
1. Build the facts and print the successful tools:
   ```bash
   .venv/Scripts/python tools/facts.py build
   .venv/Scripts/python tools/facts.py get tools
   ```
2. Choose **6–9 features**. Use only tools that succeeded at least once, and use their exact names. Suggested families, in reveal order:

   | Family | Tool(s) |
   |---|---|
   | look around | `studio_status`, `list_models` |
   | wake a model | `load_model` |
   | images | `generate_image` |
   | video | `generate_video` + `get_job` (the queue) |
   | voice | `generate_audio` (clone/speak) |
   | separation | `generate_audio` separate |
   | listening | `transcribe` |
   | learning | `start_training` |
   | export | `export_model` (GGUF) |
   | the new model speaks | `chat` |

   You can only pick training/export after P6-T09 has run them in production. For now, mark those two `pending`; their evidence from P2-T13 already exists.
3. Write `script/features.json`:
   ```json
   {"features": [
     {"id": "f01", "tools": ["load_model"], "title": "load_model",
      "line": "plain-words description from TOOLS.md", "evidence_seq": [12],
      "metaphor": "one-line visual idea", "status": "ok|pending"}
   ]}
   ```
   - `title` is what appears on screen. It must be a real tool name, or a value that already exists in `facts.json`.
4. Rebuild with `facts.py build`, which merges the features. Then run `facts.py check "<title>"` for every title; all must pass.

## Outputs
- `script/features.json`, refreshed `edit/facts.json`.

## Done when
- [ ] There are 6–9 features with evidence seqs.
- [ ] Every title passes `facts.py check`.

## STATUS line
`P5-T01 DONE · 8 features (f01–f08), all titles verified` (example)
