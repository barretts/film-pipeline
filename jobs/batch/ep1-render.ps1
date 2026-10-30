# Owner GO 2026-10-30: episode 1 render batch.
# kill Strata -> James orbit upgrade -> run episode 1 (synchronous P.run) -> evidence (ffprobe + contact sheet) -> Codex restore.
$ErrorActionPreference = 'Continue'
Set-Location F:\film-pipeline
$ev = 'jobs\batch\evidence.txt'
function Rec($m) { "$(Get-Date -Format s) $m" | Out-File $ev -Append -Encoding unicode }
$py = 'C:\Users\barrett\AppData\Local\Programs\Python\Python313\python.exe'
$style = 'Cold blue-white cinematic realism with warm lamp accents, 35mm grain.'
$env:PATH = 'C:\Users\barrett\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin;' + $env:PATH
Rec 'ep1-batch-start'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File jobs\orbit-smoke\kill-strata.ps1
if ($LASTEXITCODE -ne 0) { Rec 'kill-strata failed; aborting'; exit 1 }
$deadline = (Get-Date).AddSeconds(120)
while ($true) {
    $free = [int]((nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits) | Select-Object -First 1)
    if ($free -ge 12000) { break }
    if ((Get-Date) -ge $deadline) { Rec "GPU stuck at $free MiB; aborting"; exit 1 }
    Start-Sleep 5
}
Rec "gpu-clear free=$free"
Remove-Item -Force series\characters\james\character.json -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force series\characters\james\refs -ErrorAction SilentlyContinue
& $py tools\create_character.py --name "James" --create --voice joe --description "New recruit with a background in signal analysis who becomes obsessed with the anomaly's origin." --appearance "Man in his late twenties, dark curly hair under an ear-flap hat, clean-shaven angular face, orange-red survival suit over thermal layers." --style $style --add-to-show signal-in-the-snow --portrait series\characters\james\portrait.png *>> $ev
Rec "james-orbit-upgrade exit=$LASTEXITCODE"
$rlog = 'jobs\batch\ep1-render.log'
& $py tools\make_series.py run --show signal-in-the-snow --episode 01-signal-in-the-snow-episode-1 *> $rlog
$code = $LASTEXITCODE
Rec "ep1-render exit=$code"
$jobLine = Select-String -Path $rlog -Pattern 'Rendering job: (.+)' | Select-Object -First 1
if ($jobLine) {
    $job = ($jobLine.Matches[0].Groups[1].Value).Trim()
    Rec "job=$job"
    $mp4 = Join-Path $job 'review\assembled.mp4'
    if (Test-Path $mp4) {
        & ffprobe -v error -show_streams -show_format -of json $mp4 > jobs\batch\ep1-ffprobe.json
        Rec "ffprobe exit=$LASTEXITCODE"
        & $py tools\contact_sheet.py --videos "$mp4" --frames 12 --out jobs\batch\ep1-contact-sheet.png --title 'Episode 1 assembled' *>> $ev
        Rec "contact-sheet exit=$LASTEXITCODE"
        if (Test-Path (Join-Path $job 'review\quality.md')) { Rec 'quality.md present' }
        if (Test-Path (Join-Path $job 'continuity.json')) { Rec 'continuity.json present' }
    } else { Rec 'assembled.mp4 MISSING' }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File jobs\orbit-smoke\run.ps1 -RestoreOnly *>> $ev
Rec "restore exit=$LASTEXITCODE"
