# Post-Strata orbit smoke watchdog. Started detached; keeps GPU clear for the
# orbit test (reaping any Strata respawn - the owner ordered the serving stack
# down) and writes evidence, then restores Strata.
Set-Location F:\film-pipeline
$log='jobs\orbit-smoke\smoke.log'
New-Item -ItemType Directory -Force -Path jobs\orbit-smoke | Out-Null
function Kill-Strata{
 Get-Process strata -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
 Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*serve*server.py*' -and $_.CommandLine -like '*strata*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
# 1) wait for the serving stack to actually die (it kills me when it goes)
$t0=Get-Date
while (((Get-Date)-$t0).TotalSeconds -lt 900){
 $p=@(Get-Process strata -ErrorAction SilentlyContinue)
 $s=@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*serve*server.py*' -and $_.CommandLine -like '*strata*' })
 if(-not $p -and -not $s){break}
 if(-not $p){Kill-Strata}  # engine vanished, server still up -> finish the job
 Start-Sleep 2
}
Start-Sleep 8
# 2) run the orbit smoke (piper CPU + H3 GPU ~6-8 min), reaping respawns meanwhile
python jobs\orbit-smoke\smoke_orbit.py *> $log
$code=$LASTEXITCODE
"orbit-smoke exit=$code $(Get-Date -Format s)" | Out-File jobs\orbit-smoke\evidence.txt -Append
if($code -eq 0){Remove-Item -Recurse -Force jobs\scratch-orbit -ErrorAction SilentlyContinue; Remove-Item -Force jobs\smoke_orbit.py -ErrorAction SilentlyContinue}
# 3) GPU is ours again: restart Strata exactly as it was launched
Start-Process -FilePath 'E:\strata\Strata\.venv\Scripts\python.exe' -ArgumentList '"E:\strata\Strata\serve\server.py"','--engine','strata','--config','"E:\strata\Strata\strata-unsloth-ud-q4_k_xl-128k.json"','--port','1234' -WindowStyle Hidden -WorkingDirectory 'E:\strata\Strata'
"strata-restarted $(Get-Date -Format s)" | Out-File jobs\orbit-smoke\evidence.txt -Append
