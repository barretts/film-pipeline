# P1-T03 offline redactor test — PowerShell (py -3 works here; feeds UTF-8 via RedirectStandardInput).
# Throwaway temp dir only; real logs/ untouched (CLAUDE_PROJECT_DIR redirected). No network, no install.
$ErrorActionPreference = "Stop"
$T = Join-Path $env:TEMP "hooktest"
if (Test-Path $T) { Remove-Item -Recurse -Force $T }
New-Item -ItemType Directory -Force -Path (Join-Path $T "logs") | Out-Null
$env:CLAUDE_PROJECT_DIR = $T
$script = "F:\film-pipeline\tools\log_mcp.py"
$sample = "F:\film-pipeline\logs\tasks\p1t03_sample.json"
$other  = "F:\film-pipeline\logs\tasks\p1t03_other.json"

function RunPy($mode, $file) {
  Start-Process -FilePath "py" -ArgumentList @("-3", $script, $mode) `
    -RedirectStandardInput $file -NoNewWindow -Wait
}

Write-Output "=== POST (standalone) ==="
RunPy "post" $sample
$line = Get-Content (Join-Path $T "logs\mcp_calls.jsonl") -Encoding UTF8 | Select-Object -Last 1
Write-Output $line

Write-Output "=== pre (t_start) then post (duration_s) ==="
RunPy "pre" $sample
Start-Sleep -Milliseconds 300
RunPy "post" $sample
$line2 = Get-Content (Join-Path $T "logs\mcp_calls.jsonl") -Encoding UTF8 | Select-Object -Last 1
Write-Output $line2

Write-Output "=== non-unsloth call must be ignored ==="
RunPy "post" $other
$total = (Get-Content (Join-Path $T "logs\mcp_calls.jsonl") -Encoding UTF8 | Measure-Object -Line).Lines
Write-Output "lines_total=$total (expect 2)"

Write-Output "=== secret scan (expect none) ==="
$raw = Join-Path $T "logs\mcp_raw"
$files = @((Join-Path $T "logs\mcp_calls.jsonl")) + (Get-ChildItem $raw -File | ForEach-Object FullName)
$leak = Select-String -Path $files -Pattern 'sk-unsloth-[A-Za-z0-9]' -Encoding UTF8
if ($leak) { Write-Output "LEAK!"; $leak } else { Write-Output "no keys in logs" }

Write-Output "=== raw dir listing ==="
Get-ChildItem $raw | Select-Object Name, Length | Format-Table -AutoSize | Out-String | Write-Output

Write-Output "=== assertions ==="
$all = (Get-Content (Join-Path $T "logs\mcp_calls.jsonl") -Encoding UTF8) -join "`n"
if ($all -match '"tool": *"selftest"')            { Write-Output "OK tool=selftest" }        else { Write-Output "FAIL tool" }
if ($all -match '"api_key": *"<redacted>"')       { Write-Output "OK api_key redacted" }     else { Write-Output "FAIL redaction" }
if ($all -match '"max_tokens": *64')              { Write-Output "OK max_tokens kept" }      else { Write-Output "FAIL max_tokens" }
if ($all -match 'caf')                            { Write-Output "OK note present" }         else { Write-Output "FAIL note absent" }
if ($all -match '"ok": *true')                    { Write-Output "OK ok=true" }              else { Write-Output "FAIL ok" }
if ($all -match '"duration_s"')                   { Write-Output "OK duration_s present" }   else { Write-Output "FAIL duration" }
