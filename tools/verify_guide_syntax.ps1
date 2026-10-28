$text = Get-Content -LiteralPath .\LOCAL_FILM_INSTALL_GUIDE.md -Raw
$matches = [regex]::Matches($text, '(?s)```powershell\s*\r?\n(.*?)```')
$bad = 0
foreach ($m in $matches) {
  $tokens = $null
  $parseErrors = $null
  [System.Management.Automation.Language.Parser]::ParseInput($m.Groups[1].Value, [ref]$tokens, [ref]$parseErrors) | Out-Null
  if ($parseErrors.Count -gt 0) { $bad += $parseErrors.Count; $parseErrors | ForEach-Object { Write-Output $_.Message } }
}
Write-Output "PowerShell blocks: $($matches.Count), syntax errors: $bad"
if ($bad -gt 0) { exit 1 }
