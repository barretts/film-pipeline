$ErrorActionPreference = 'Stop'
# ASCII-only source; the non-ASCII note is built from char codes so this file has no ANSI ambiguity.
$note = 'caf' + [char]0xE9 + ' ' + [char]0xD7 + ' ' + [char]0x201C + 'q' + [char]0x201D
$api  = 'sk-unsloth-TEST'
$sample = 'F:\film-pipeline\logs\tasks\p1t03_sample.json'
$json = '{"tool_name":"mcp__unsloth_studio__selftest","tool_use_id":"t1","tool_input":{"api_key":"' + $api + '","max_tokens":64,"note":"' + $note + '"},"tool_response":{"ok":true,"data":{"media_url":"F:/film-pipeline/stills/x.png","count":3}}}'
[IO.File]::WriteAllText($sample, $json, (New-Object System.Text.UTF8Encoding($false)))
$rb = [IO.File]::ReadAllBytes($sample)
Write-Output ('file_bytes=' + $rb.Length)
$u8 = $false
for ($i = 0; $i -lt $rb.Length - 1; $i++) { if ($rb[$i] -eq 0xC3 -and $rb[$i+1] -eq 0xA9) { $u8 = $true; break } }
if ($u8) { Write-Output 'FILE_IS_UTF8 (C3 A9 present)' } else { Write-Output 'FILE_NOT_UTF8 (ANSI)' }
$T = Join-Path $env:TEMP 'h4'
if (Test-Path $T) { Remove-Item -Recurse -Force $T }
New-Item -ItemType Directory -Force (Join-Path $T 'logs') | Out-Null
$env:CLAUDE_PROJECT_DIR = $T
& cmd /c ('type ' + $sample + ' | py -3 F:\film-pipeline\tools\log_mcp.py post')
$line = (Get-Content (Join-Path $T 'logs\mcp_calls.jsonl') -Encoding UTF8 | Select-Object -Last 1)
Write-Output ('LINE=' + $line)
if ($line.Contains($note)) { Write-Output 'UTF8_ROUNDTRIP_OK' } else { Write-Output 'UTF8_ROUNDTRIP_FAIL' }
if ($line.Contains('<redacted>')) { Write-Output 'REDACT_OK' } else { Write-Output 'REDACT_FAIL' }
