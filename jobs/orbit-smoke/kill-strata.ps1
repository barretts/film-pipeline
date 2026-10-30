# Owner-ordered self-shutdown: kill engine + BOTH levels of the serve/server.py
# supervisor chain, verified. Lives in a file so bash never expands $_.
$ErrorActionPreference = 'Stop'
$targets = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'serve[\\/]server\.py' -and $_.CommandLine -match 'strata' })
foreach ($p in $targets) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Stop-Process -Name strata -Force -ErrorAction SilentlyContinue
$deadline = (Get-Date).AddSeconds(30)
do {
    Stop-Process -Name strata -Force -ErrorAction SilentlyContinue
    Start-Sleep 1
    $servers = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'serve[\\/]server\.py' -and $_.CommandLine -match 'strata' })
    $engines = @(Get-Process strata -ErrorAction SilentlyContinue)
} while (($servers.Count -or $engines.Count) -and (Get-Date) -lt $deadline)
$log = 'F:\film-pipeline\jobs\orbit-smoke\kill.log'
"$(Get-Date -Format s) killed_servers=$($targets.Count) servers_left=$($servers.Count) engine_left=$($engines.Count)" | Out-File $log -Append -Encoding unicode
if ($servers.Count -or $engines.Count) { throw 'Strata shutdown incomplete; inspect kill.log. Do not start the GPU job.' }
