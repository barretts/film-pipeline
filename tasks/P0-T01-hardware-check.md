# P0-T01 · Hardware check

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN (the agent reviews later) | — | none | 10 min | — |

**Goal:** confirm the PC matches CONTEXT §2 and choose the drive for models (≥ 250 GB free, SSD/NVMe).

## Steps
1. **[HUMAN · PowerShell]** Open PowerShell in this package folder and run the read-only checker:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\check-film-pc.ps1 -ModelDrive X -Json
   ```
   Replace `X` with the drive you plan to use for models. Results go to `tools\check-film-pc.json`.
2. Expected results:
   - `[OK]` for the GPU (16 GB tier), RAM (~128 GB) and the drive (≥ 250 GB free).
   - A `[NOTE]` about the PCIe Gen 3 link.
   - `[FIX]` lines for missing tools are fine for now; P0-T02 fixes them.
3. **[HUMAN]** Write the model drive letter into the STATUS.md header ("Model drive").
4. **(AGENT, at the start of P0-T04)** Read only the verdict, not the whole JSON:
   ```bash
   py -3 -c "import json;d=json.load(open('tools/check-film-pc.json',encoding='utf-8-sig'));print(json.dumps(d['verdict'],indent=1))"
   ```
   Put a one-line summary in `logs/tasks/P0-T01.md`.

## Outputs
- `tools/check-film-pc.json`
- Model drive letter in STATUS.md

## Done when
- [ ] There are no `[FIX]` lines about the GPU, RAM or disk.
- [ ] The chosen drive is an SSD/NVMe (the script shows its BusType/MediaType).

## If it fails
- **The chosen drive is a hard disk:** pick another drive if possible. Otherwise accept slow first loads; 128 GB RAM caches files after that. Record the choice in Decisions.
- **VRAM shows under 15 GB:** update the NVIDIA driver (P0-T03 step 1) and run the check again.

## STATUS line
`P0-T01 DONE · 16 GB GPU, 128 GB RAM, X: 400 GB free NVMe` (example)
