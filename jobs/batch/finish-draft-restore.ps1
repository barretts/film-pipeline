# Owner picks 2026-10-30: kate -> portrait-candidate-3 + kristin, james -> portrait-candidate-1 + joe.
# Batch: kill Strata (standing authorization) -> finish both characters (orbit refs; smoke-proven path)
# -> draft episode 1 (CPU llama.cpp, safe while GPU idle) -> restore Strata via the Codex-repaired watchdog
# (-RestoreOnly: verifies ComfyUI idle, unloads idle models, launches server, probes inference).
$ErrorActionPreference = 'Continue'
Set-Location F:\film-pipeline
$evDir = 'jobs\batch'; New-Item -ItemType Directory -Force -Path $evDir | Out-Null
$ev = Join-Path $evDir 'evidence.txt'
function Rec($m) { "$(Get-Date -Format s) $m" | Out-File $ev -Append -Encoding unicode }
$py = 'C:\Users\barrett\AppData\Local\Programs\Python\Python313\python.exe'
$style = 'Cold blue-white cinematic realism with warm lamp accents, 35mm grain.'
Rec 'batch1-start'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File jobs\orbit-smoke\kill-strata.ps1
if ($LASTEXITCODE -ne 0) { Rec 'kill-strata failed; aborting batch'; exit 1 }
$deadline = (Get-Date).AddSeconds(120)
while ($true) {
    $free = [int]((nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) | Select-Object -First 1)
    if ($free -ge 12000) { break }
    if ((Get-Date) -ge $deadline) { Rec "GPU free stuck at $free MiB; aborting batch"; exit 1 }
    Start-Sleep 5
}
Rec "gpu-clear free=$free"
& $py tools\create_character.py --name "Kate" --create --voice kristin --description "Senior radio operator who has spent a decade at the polar post and keeps its fragile reality intact." --appearance "Woman in her late forties, short silver-streaked brown hair, weathered fair skin, navy wool work jacket over a cream sweater, brass ring on a lanyard." --style $style --add-to-show signal-in-the-snow --portrait series\characters\kate\portrait-candidate-3.png *>> $ev
Rec "kate exit=$LASTEXITCODE"
& $py tools\create_character.py --name "James" --create --voice joe --description "New recruit with a background in signal analysis who becomes obsessed with the anomaly's origin." --appearance "Man in his late twenties, dark curly hair under an ear-flap hat, clean-shaven angular face, orange-red survival suit over thermal layers." --style $style --add-to-show signal-in-the-snow --portrait series\characters\james\portrait-candidate-1.png *>> $ev
Rec "james exit=$LASTEXITCODE"
$brief = 'Episode 1: In a cramped, frost-bitten control room bathed in the glow of monitors and the warm amber of desk lamps, senior operator Kate and new recruit James spend a sleepless night tracking an impossible frequency that pulses with a rhythmic, human-like cadence, only for James to vanish into the blizzard outside the reinforced glass just as the signal shifts from noise to a distinct, repeating phrase that sounds suspiciously like a name. Ends: James is gone, but the signal has locked onto his location, pulling the remaining operator Kate toward the coordinates where the ice begins to hum in response.'
& $py tools\make_series.py new-episode --show signal-in-the-snow --number 1 --duration 60 --brief $brief *>> $ev
Rec "ep1-draft exit=$LASTEXITCODE"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File jobs\orbit-smoke\run.ps1 -RestoreOnly *>> $ev
Rec "restore exit=$LASTEXITCODE"
