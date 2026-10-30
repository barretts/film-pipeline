# Owner-ordered self-shutdown: kill engine + BOTH levels of the serve/server.py
# supervisor chain, verified. Lives in a file so bash never expands $_.
$targets = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'serve[\\/]server\.py' -and $_.CommandLine -match 'strata' }
foreach ($p in $targets) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Stop-Process -Name strata -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Stop-Process -Name strata -Force -ErrorAction SilentlyContinue
$log = 'F:\film-pipeline\jobs\orbit-smoke\kill.log'
"$(Get-Date -Format s) killed_servers=$($targets.Count) engine_left=$(@(Get-Process strata -ErrorAction SilentlyContinue).Count)" | Out-File $log -Append
