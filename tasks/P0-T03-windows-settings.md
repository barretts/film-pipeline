# P0-T03 · Windows settings + model drive

| Who | Needs | GPU model | Time | ✋ |
|---|---|---|---|---|
| HUMAN | P0-T02 | none | 20–30 min (+ reboot) | — |

**Goal:** a current driver, Windows ready for large model files and deep paths, no sleep during long runs, and model downloads going to the big drive.

## Steps
1. **NVIDIA driver:** update to the latest Game Ready or Studio driver (NVIDIA App or nvidia.com), then reboot.
2. **Developer Mode:** Settings › System › For developers › Developer Mode **On**. This lets the Hugging Face cache use symlinks instead of duplicate copies.
3. **Long paths** (admin PowerShell):
   ```powershell
   New-ItemProperty -Path HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
   ```
4. **Page file:** System › About › Advanced system settings › Performance › Settings › Advanced › Virtual memory. Tick **"Automatically manage paging file size for all drives"**.
5. **No sleep while plugged in**, so overnight queues and multi-hour downloads keep running:
   ```powershell
   powercfg /change standby-timeout-ac 0
   powercfg /change hibernate-timeout-ac 0
   ```
   Also pause updates for the project (Settings › Windows Update › Pause updates, 2–3 weeks) so the PC doesn't restart overnight. Undo both after the project.
6. **Model cache on the big drive.** Replace `X` with your drive letter:
   ```powershell
   setx HF_HOME X:\hf
   ```
   Open a new terminal and check it with `echo $env:HF_HOME`.
7. During long runs, close game launchers, overlays and heavy browser tabs. They take VRAM.
8. Re-run the checker:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\check-film-pc.ps1 -ModelDrive X -Json
   ```

## Outputs
- Windows settings applied, `HF_HOME` set.

## Done when
- [ ] The checker shows **no `[FIX]` lines**.
- [ ] The checker shows **no `[NOTE]` lines about long paths, Developer Mode or the page file**.
- [ ] `HF_HOME` points at the model drive.
- [ ] Sleep and hibernate on AC power are set to never.

## If it fails
- **No admin rights for long paths:** ask whoever manages the PC. Until then, keep the project path short, e.g. `X:\film`.
- **Policy blocks Developer Mode:** skip it, and keep extra free disk space for duplicate files.

## STATUS line
`P0-T03 DONE · driver updated, dev mode, long paths, no sleep, HF_HOME=X:\hf` (example)
