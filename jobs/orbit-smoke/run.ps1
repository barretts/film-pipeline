# Run detached before stopping Strata. Continue OMP manually after restoration.
[CmdletBinding()]
param([switch]$RestoreOnly, [int]$ReadyTimeoutSeconds = 900)
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path "$PSScriptRoot\..\..")
$evidence = Join-Path $PSScriptRoot 'evidence.txt'
$configPath = 'E:\strata\Strata\strata-unsloth-ud-q4_k_xl-128k.json'
function Record($message) { "$(Get-Date -Format s) $message" | Out-File $evidence -Append -Encoding unicode }
function ServingProcesses {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
        $_.CommandLine -match 'serve[\\/]server\.py' -and $_.CommandLine -match 'strata'
    })
}
$lock = $null
try {
    # One watchdog owns shutdown, rendering, and restoration at a time.
    $lock = [IO.File]::Open((Join-Path $PSScriptRoot 'watchdog.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    Record "watchdog-start restoreOnly=$RestoreOnly"
    $smokeError = $null
    if (-not $RestoreOnly) {
        try {
            $deadline = (Get-Date).AddSeconds(900)
            while ((Get-Process strata -ErrorAction SilentlyContinue) -or (ServingProcesses)) {
                if ((Get-Date) -ge $deadline) { throw 'Shutdown timed out; smoke was not started.' }
                Start-Sleep 2
            }
            Start-Sleep 8
            & "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe" "$PSScriptRoot\smoke_orbit.py" > "$PSScriptRoot\smoke.log" 2>&1
            $code = $LASTEXITCODE
            Record "orbit-smoke exit=$code"
            if ($null -eq $code -or $code -ne 0) { throw 'Orbit smoke failed; inspect smoke.log.' }
            # Preserve scratch frames for inspection.
        } catch {
            $smokeError = $_
            Record "orbit-smoke failed: $($_.Exception.Message)"
        }
    }
    $cfg = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $headers = @{}
    if ($cfg.api_key) { $headers.Authorization = 'Bearer ' + $cfg.api_key }
    $base = 'http://127.0.0.1:1234'
    $alreadyReady = $false
    try {
        $health = Invoke-RestMethod "$base/health" -Headers $headers -TimeoutSec 5
        $alreadyReady = [bool]$health.loaded
    } catch { }
    if (-not $alreadyReady) {
        $queue = Invoke-RestMethod 'http://127.0.0.1:8191/queue' -TimeoutSec 10
        if ($queue.queue_running.Count -or $queue.queue_pending.Count) {
            throw 'ComfyUI has active/pending jobs; refusing to unload their models.'
        }
        Invoke-RestMethod 'http://127.0.0.1:8191/free' -Method Post -ContentType 'application/json' -Body '{"unload_models":true,"free_memory":true}' -TimeoutSec 30 | Out-Null
        Start-Sleep 5
        Record 'comfy-idle-models-unloaded'
        if (-not (ServingProcesses)) {
            if (Get-Process strata -ErrorAction SilentlyContinue) { throw 'Orphan Strata engine exists; refusing a duplicate launch.' }
            $arguments = @('"E:\strata\Strata\serve\server.py"', '--engine', 'strata', '--config', ('"' + $configPath + '"'), '--port', '1234')
            $server = Start-Process 'E:\strata\Strata\.venv\Scripts\python.exe' -ArgumentList $arguments -WorkingDirectory 'E:\strata\Strata' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot\strata-stdout.log" -RedirectStandardError "$PSScriptRoot\strata-stderr.log"
            Record "strata-start-requested pid=$($server.Id)"
        }
        $deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)
        while ($true) {
            try {
                $health = Invoke-RestMethod "$base/health" -Headers $headers -TimeoutSec 5
                if ($health.loaded) { break }
            } catch { }
            if ((Get-Date) -ge $deadline) { throw 'Strata readiness timed out; inspect strata-stdout.log and strata-stderr.log.' }
            if (-not (ServingProcesses)) { throw 'Strata server exited before readiness; inspect strata-stderr.log and the engine log.' }
            Start-Sleep 5
        }
    }
    $body = @{ model = $cfg.model_name; messages = @(@{ role = 'user'; content = 'Reply with OK.' }); max_tokens = 16; stream = $false } | ConvertTo-Json -Depth 5
    $reply = Invoke-RestMethod "$base/v1/chat/completions" -Headers $headers -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 180
    if (-not $reply.choices -or $reply.choices[0].finish_reason -eq 'error') { throw 'Strata inference probe failed.' }
    Record 'strata-ready inference=passed; manually continue the existing OMP session'
    Write-Output 'Strata restored and inference verified. Continue OMP manually with c or a new prompt.'
    if ($smokeError) { throw $smokeError }
} catch {
    if ($lock) { Record "watchdog-failed: $($_.Exception.Message)" }
    throw
} finally {
    if ($lock) { $lock.Dispose() }
}
