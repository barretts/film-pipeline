# Extract specific frames from a render for scoring. Usage:
#   extract-frames.ps1 <mp4-path> <out-prefix> <frames...>
# e.g. extract-frames.ps1 comfy-local/output/phase0/S1-listen-together_00001.mp4 jobs/phase0-rigid-llm/results/s1-s2-check/S1 0 1 5 10 24 72 123
param(
    [Parameter(Mandatory=$true)][string]$Video,
    [Parameter(Mandatory=$true)][string]$Prefix,
    [Parameter(Mandatory=$true, ValueFromRemainingArguments=$true)][int[]]$Frames
)
Set-Location F:\film-pipeline
foreach ($f in $Frames) {
    $out = "{0}-f{1}.png" -f $Prefix, $f
    $filter = "select='eq(n,{0})'" -f $f
    ffmpeg -v error -y -i $Video -vf $filter -vframes 1 $out
    if (Test-Path $out) {
        Write-Output ("OK {0} {1} bytes" -f $out, (Get-Item $out).Length)
    } else {
        Write-Output ("FAIL {0}" -f $out)
    }
}
