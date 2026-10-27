<#
  check-film-pc.ps1
  Read-only readiness check for the local AI film pipeline
  (local coding client + Unsloth Studio MCP + local models + HyperFrames).

  It makes NO changes to your PC. It reports:
    - GPU, VRAM, driver, CUDA version and PCIe link
    - RAM, CPU, disks (free space, SSD/HDD)
    - Windows settings that matter (page file, long paths, Developer Mode, HF_HOME)
    - Whether common tools are installed (git, node 22+, ffmpeg, python, claude, unsloth)
  ...and ends with an [OK] / [FIX] / [NOTE] list.

  Run it from PowerShell in the folder that contains this file:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\check-film-pc.ps1
  Options:
    -ModelDrive D   check free space on the drive you plan to keep models on
    -Json           also save the results to check-film-pc.json next to this script
#>
[CmdletBinding()]
param(
    [string]$ModelDrive = '',
    [switch]$Json
)

Set-StrictMode -Off
$ErrorActionPreference = 'Continue'

$report   = [ordered]@{ checked_at = (Get-Date).ToString('s') }
$goods    = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$notes    = New-Object System.Collections.Generic.List[string]

$NeedDiskGB   = 250   # models + work files
$NeedNodeMajor = 22   # HyperFrames requirement

# ---------- helpers ----------
function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host ('== ' + $Title + ' ==') -ForegroundColor Cyan
}

function Write-Item([string]$Label, $Value) {
    if ($null -eq $Value -or "$Value" -eq '') { $Value = 'unknown' }
    Write-Host ('  {0,-28} {1}' -f ($Label + ':'), $Value)
}

function ConvertTo-NumberOrNull($Text) {
    $d = 0.0
    if ($null -ne $Text -and [double]::TryParse(("$Text").Trim(), [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$d)) { return $d }
    return $null
}

function Convert-RegToUInt64($Val) {
    if ($null -eq $Val) { return $null }
    if ($Val -is [byte[]]) {
        if ($Val.Length -ge 8) { return [BitConverter]::ToUInt64($Val, 0) }
        if ($Val.Length -ge 4) { return [uint64][BitConverter]::ToUInt32($Val, 0) }
        return $null
    }
    try { return [uint64]$Val } catch { return $null }
}

function Get-FirstLine([string]$Exe, [string[]]$ArgList) {
    try {
        $out = & $Exe @ArgList 2>&1 | Select-Object -First 1
        if ($null -ne $out) { return ("$out").Trim() }
    } catch { }
    return $null
}

function Get-Tool([string]$Name, [string[]]$ArgList) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $cmd) { return [ordered]@{ found = $false; path = $null; version = $null } }
    $path = $cmd.Source
    if (-not $path) { $path = $cmd.Definition }
    # Windows ships 'python' / 'python3' aliases that only open the Microsoft Store
    if ($path -and $path -like '*\WindowsApps\python*.exe') {
        return [ordered]@{ found = $false; path = $path; version = 'Microsoft Store alias only (Python not installed)' }
    }
    $ver = $null
    if ($ArgList -and $ArgList.Count -gt 0) { $ver = Get-FirstLine $path $ArgList }
    return [ordered]@{ found = $true; path = $path; version = $ver }
}

# ---------- Windows ----------
Write-Section 'Windows'
$os = $null
try { $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop } catch { }
if ($os) {
    $report.os = [ordered]@{ name = $os.Caption; version = $os.Version; build = $os.BuildNumber }
    Write-Item 'Edition' $os.Caption
    Write-Item 'Version' $os.Version
} else {
    $report.os = $null
    Write-Item 'Edition' $null
    $notes.Add('Could not read Windows details. Run this script on the Windows PC itself.')
}

# ---------- CPU ----------
Write-Section 'CPU'
$cpu = $null
try { $cpu = Get-CimInstance Win32_Processor -ErrorAction Stop | Select-Object -First 1 } catch { }
if ($cpu) {
    $cpuName = ("$($cpu.Name)").Trim()
    $report.cpu = [ordered]@{ name = $cpuName; cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors }
    Write-Item 'Model' $cpuName
    Write-Item 'Cores / threads' ('{0} / {1}' -f $cpu.NumberOfCores, $cpu.NumberOfLogicalProcessors)
} else {
    $report.cpu = $null
    Write-Item 'Model' $null
}

# ---------- RAM ----------
Write-Section 'Memory (RAM)'
$ramGB = $null
try {
    $cs = Get-CimInstance Win32_ComputerSystem -ErrorAction Stop
    $ramGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
} catch { }
$dimms = @()
try { $dimms = @(Get-CimInstance Win32_PhysicalMemory -ErrorAction Stop) } catch { }
$ramSpeed = $null
if ($dimms.Count -gt 0) {
    $speeds = @($dimms | ForEach-Object { if ($_.ConfiguredClockSpeed) { $_.ConfiguredClockSpeed } else { $_.Speed } } | Where-Object { $_ })
    if ($speeds.Count -gt 0) { $ramSpeed = ($speeds | Measure-Object -Minimum).Minimum }
}
$report.ram = [ordered]@{ total_gb = $ramGB; modules = $dimms.Count; speed_mts = $ramSpeed }
Write-Item 'Installed' $(if ($null -ne $ramGB) { "$ramGB GB" } else { $null })
Write-Item 'Modules' $(if ($dimms.Count -gt 0) { $dimms.Count } else { $null })
Write-Item 'Speed (MT/s)' $ramSpeed

# ---------- GPU ----------
Write-Section 'GPU'
$regGpus = New-Object System.Collections.Generic.List[object]
$classKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
try {
    $subKeys = @(Get-ChildItem -Path $classKey -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^\d{4}$' })
    foreach ($k in $subKeys) {
        $p = Get-ItemProperty -Path $k.PSPath -ErrorAction SilentlyContinue
        if ($p -and $p.DriverDesc) {
            $bytes = Convert-RegToUInt64 $p.'HardwareInformation.qwMemorySize'
            if (-not $bytes) { $bytes = Convert-RegToUInt64 $p.'HardwareInformation.MemorySize' }
            $vram = $null
            if ($bytes) { $vram = [math]::Round($bytes / 1GB, 1) }
            $regGpus.Add([ordered]@{ name = "$($p.DriverDesc)"; vram_gb = $vram; driver = "$($p.DriverVersion)" })
        }
    }
} catch { }

$nvGpus = New-Object System.Collections.Generic.List[object]
$cudaVer = $null
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue | Select-Object -First 1
if ($smi) {
    try {
        $fields = 'name,memory.total,memory.used,driver_version,pcie.link.gen.max,pcie.link.gen.current,pcie.link.width.max,pcie.link.width.current'
        $lines = @(& $smi.Source "--query-gpu=$fields" '--format=csv,noheader,nounits' 2>$null)
        foreach ($line in $lines) {
            if (-not $line) { continue }
            $v = @(("$line").Split(',') | ForEach-Object { $_.Trim() })
            if ($v.Count -lt 8) { continue }
            $totMiB  = ConvertTo-NumberOrNull $v[1]
            $usedMiB = ConvertTo-NumberOrNull $v[2]
            $nvGpus.Add([ordered]@{
                name           = $v[0]
                vram_gb        = $(if ($null -ne $totMiB) { [math]::Round($totMiB / 1024, 1) } else { $null })
                used_gb        = $(if ($null -ne $usedMiB) { [math]::Round($usedMiB / 1024, 1) } else { $null })
                driver         = $v[3]
                pcie_gen_max   = $v[4]
                pcie_gen_now   = $v[5]
                pcie_width_max = $v[6]
                pcie_width_now = $v[7]
            })
        }
        $hdr = (@(& $smi.Source 2>$null) -join "`n")
        if ($hdr -match 'CUDA Version:\s*([0-9.]+)') { $cudaVer = $Matches[1] }
    } catch { }
}

if ($nvGpus.Count -gt 0) {
    foreach ($g in $nvGpus) {
        Write-Item 'NVIDIA GPU' $g.name
        Write-Item '  VRAM total / in use' ('{0} GB / {1} GB' -f $g.vram_gb, $g.used_gb)
        Write-Item '  Driver' $g.driver
        Write-Item '  PCIe link (max)' ('Gen {0} x{1}' -f $g.pcie_gen_max, $g.pcie_width_max)
        Write-Item '  PCIe link (now)' ('Gen {0} x{1}  (drops at idle; normal)' -f $g.pcie_gen_now, $g.pcie_width_now)
    }
    Write-Item 'CUDA (driver supports)' $cudaVer
} elseif ($regGpus.Count -gt 0) {
    foreach ($g in $regGpus) { Write-Item 'Display adapter' ('{0}  ({1} GB)' -f $g.name, $g.vram_gb) }
    Write-Item 'nvidia-smi' 'not found'
} else {
    Write-Item 'GPU' $null
}
$report.gpu = [ordered]@{ nvidia = $nvGpus; adapters = $regGpus; cuda = $cudaVer }

# ---------- Disks ----------
Write-Section 'Disks'
$diskInfo = New-Object System.Collections.Generic.List[object]
$logical = @()
try { $logical = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop) } catch { }
foreach ($d in $logical) {
    $letter = ("$($d.DeviceID)").TrimEnd(':')
    $media = $null; $bus = $null
    try {
        $part = Get-Partition -DriveLetter $letter -ErrorAction Stop | Select-Object -First 1
        $pd = Get-PhysicalDisk -ErrorAction Stop | Where-Object { "$($_.DeviceId)" -eq "$($part.DiskNumber)" } | Select-Object -First 1
        if ($pd) { $media = "$($pd.MediaType)"; $bus = "$($pd.BusType)" }
    } catch { }
    $free = [math]::Round($d.FreeSpace / 1GB, 0)
    $size = [math]::Round($d.Size / 1GB, 0)
    $diskInfo.Add([ordered]@{ drive = $letter; free_gb = $free; size_gb = $size; media = $media; bus = $bus })
    Write-Item ($letter + ':') ('{0} GB free of {1} GB  {2} {3}' -f $free, $size, $bus, $media)
}
$report.disks = $diskInfo

# ---------- Windows settings ----------
Write-Section 'Windows settings'
$longPaths = $null
try { $longPaths = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction Stop).LongPathsEnabled } catch { }
$devMode = $null
try { $devMode = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -ErrorAction Stop).AllowDevelopmentWithoutDevLicense } catch { }
$pfAuto = $null
$pfMB = $null
try { $pfAuto = (Get-CimInstance Win32_ComputerSystem -ErrorAction Stop).AutomaticManagedPagefile } catch { }
try { $pfMB = (Get-CimInstance Win32_PageFileUsage -ErrorAction Stop | Measure-Object -Property AllocatedBaseSize -Sum).Sum } catch { }
$hfHome = $env:HF_HOME
if (-not $hfHome) { $hfHome = [Environment]::GetEnvironmentVariable('HF_HOME', 'User') }

Write-Item 'Long paths enabled' $(if ($longPaths -eq 1) { 'yes' } elseif ($null -ne $longPaths) { 'no' } else { $null })
Write-Item 'Developer Mode' $(if ($devMode -eq 1) { 'on' } elseif ($null -ne $devMode) { 'off' } else { 'off (not set)' })
Write-Item 'Page file' $(if ($pfAuto) { 'system-managed' } elseif ($null -ne $pfMB) { "fixed, $([math]::Round($pfMB / 1024, 1)) GB" } else { $null })
Write-Item 'HF_HOME' $(if ($hfHome) { $hfHome } else { 'not set (default: %USERPROFILE%\.cache\huggingface)' })
$report.settings = [ordered]@{ long_paths = $longPaths; developer_mode = $devMode; pagefile_auto = $pfAuto; pagefile_mb = $pfMB; hf_home = $hfHome }

# ---------- Tools ----------
Write-Section 'Tools'
$tools = [ordered]@{}
$tools.winget  = Get-Tool 'winget'  @('--version')
$tools.git     = Get-Tool 'git'     @('--version')
$tools.node    = Get-Tool 'node'    @('--version')
$tools.npx     = Get-Tool 'npx'     @()
$tools.ffmpeg  = Get-Tool 'ffmpeg'  @('-version')
$tools.py      = Get-Tool 'py'      @('-3', '--version')
$tools.python  = Get-Tool 'python'  @('--version')
$tools.claude  = Get-Tool 'claude'  @('--version')
$tools.unsloth = Get-Tool 'unsloth' @()
foreach ($name in $tools.Keys) {
    $t = $tools[$name]
    $shown = 'not found'
    if ($t.found) {
        $shown = 'found'
        if ($t.version) { $shown = $t.version }
    } elseif ($t.version) {
        $shown = $t.version
    }
    Write-Item $name $shown
}
$report.tools = $tools

# ---------- Verdict ----------
# GPU tier
$best = $null
if ($nvGpus.Count -gt 0) {
    $best = $nvGpus | Sort-Object -Property @{ Expression = { if ($null -ne $_.vram_gb) { [double]$_.vram_gb } else { 0 } } } -Descending | Select-Object -First 1
}
if ($null -eq $best) {
    $regNv = $regGpus | Where-Object { $_.name -match 'NVIDIA' } | Select-Object -First 1
    if ($regNv) {
        $warnings.Add("Found $($regNv.name) but nvidia-smi is missing. Install the latest NVIDIA driver (it includes nvidia-smi and CUDA support).")
    } else {
        $warnings.Add('No NVIDIA GPU detected. This pipeline needs an NVIDIA GPU with CUDA (16 GB recommended).')
    }
} else {
    $v = $best.vram_gb
    if ($null -eq $v)    { $notes.Add("Could not read VRAM for $($best.name).") }
    elseif ($v -ge 23)   { $goods.Add("GPU $($best.name) ($v GB): 24 GB tier. Q4 writer fits on GPU; 14B video needs only light offload.") }
    elseif ($v -ge 15)   { $goods.Add("GPU $($best.name) ($v GB): 16 GB tier. Matches this package (writer UD-Q4_K_XL with RAM offload, Wan2.2-5B, 14B video with offload).") }
    elseif ($v -ge 11)   { $warnings.Add("GPU $($best.name) ($v GB): 12 GB tier. Use a 2-3 bit writer, Q4 image GGUFs, Wan2.2-5B at 832x480; skip 14B video.") }
    else                 { $warnings.Add("GPU $($best.name) ($v GB): under 12 GB. Local video generation will be very slow or will not fit.") }

    $gmax = ConvertTo-NumberOrNull $best.pcie_gen_max
    $wmax = ConvertTo-NumberOrNull $best.pcie_width_max
    if ($null -ne $gmax -and $gmax -le 3) {
        $notes.Add("GPU link is PCIe Gen $gmax x$wmax. Offloading to system RAM runs at about half the speed of a Gen 4 slot, so prefer settings that fit in VRAM.")
    }
    if ($null -ne $wmax -and $wmax -lt 8) {
        $warnings.Add("GPU link is only x$wmax. Check that the card sits in a full-length slot wired to the CPU (x8 or x16).")
    }
    if ($null -ne $best.used_gb -and $best.used_gb -ge 1.5) {
        $notes.Add("$($best.used_gb) GB of VRAM is already in use. Close browsers, games and overlays before long runs.")
    }
}

# RAM
if ($null -eq $ramGB)   { $notes.Add('Could not read installed RAM.') }
elseif ($ramGB -ge 60)  { $goods.Add("RAM $ramGB GB: enough to offload Wan2.2-A14B / LTX-2.5 hero and talking shots.") }
elseif ($ramGB -ge 30)  { $notes.Add("RAM $ramGB GB: fine for the writer and Wan2.2-5B. Offloading 14B video models will be tight: use Q4 GGUFs, short clips and a system-managed page file. 64 GB is recommended.") }
else                    { $warnings.Add("RAM $ramGB GB: stay with models that fit in VRAM (Wan2.2-5B at 832x480). Consider upgrading to 64 GB; X399 boards have 8 DIMM slots.") }

# Disk
$target = $null
if ($ModelDrive) {
    $want = $ModelDrive.TrimEnd(':', '\').ToUpper()
    $target = $diskInfo | Where-Object { $_.drive -eq $want } | Select-Object -First 1
    if (-not $target) { $warnings.Add("Drive $want was not found.") }
}
if (-not $target -and $diskInfo.Count -gt 0) {
    $target = $diskInfo | Sort-Object -Property @{ Expression = { [double]$_.free_gb } } -Descending | Select-Object -First 1
}
if ($target) {
    if ($target.free_gb -lt $NeedDiskGB) {
        $warnings.Add("Drive $($target.drive): has $($target.free_gb) GB free; plan on about $NeedDiskGB GB for models and work files.")
    } else {
        $goods.Add("Drive $($target.drive): has $($target.free_gb) GB free (need about $NeedDiskGB GB).")
    }
    if ($target.media -eq 'HDD') {
        $warnings.Add("Drive $($target.drive): is a hard disk. Keep models on an SSD/NVMe; loading 10-30 GB files from HDD is very slow.")
    }
    if (-not $hfHome -and $target.drive -ne 'C') {
        $notes.Add("To store models on $($target.drive): run  setx HF_HOME $($target.drive):\hf  then open a new terminal.")
    }
}

# Windows settings
if ($longPaths -ne 1) { $notes.Add('Long paths are off. Enable them (admin PowerShell): New-ItemProperty -Path HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force') }
if ($devMode -ne 1)   { $notes.Add('Developer Mode is off, so the Hugging Face cache stores duplicate files instead of symlinks. Turn it on: Settings > System > For developers.') }
if ($pfAuto -eq $false -and $null -ne $pfMB -and $pfMB -lt 32768) { $notes.Add("Page file is fixed at $([math]::Round($pfMB / 1024, 1)) GB. Set it to system-managed on an SSD so large model loads do not fail.") }

# Tools
if (-not $tools.winget.found) { $notes.Add('winget not found. Install "App Installer" from the Microsoft Store, or install the tools manually.') }
if (-not $tools.git.found)    { $warnings.Add('Git missing:      winget install --id Git.Git -e') }
if (-not $tools.node.found)   { $warnings.Add('Node.js missing:  winget install --id OpenJS.NodeJS.LTS -e   (HyperFrames needs Node 22+)') }
else {
    $nodeMajor = $null
    if ($tools.node.version -match 'v?(\d+)\.') { $nodeMajor = [int]$Matches[1] }
    if ($null -ne $nodeMajor -and $nodeMajor -lt $NeedNodeMajor) { $warnings.Add("Node.js $($tools.node.version) is too old for HyperFrames (needs 22+): winget upgrade --id OpenJS.NodeJS.LTS -e") }
}
if (-not $tools.ffmpeg.found) { $warnings.Add('FFmpeg missing:   winget install --id Gyan.FFmpeg -e') }
if (-not $tools.py.found -and -not $tools.python.found) { $notes.Add('Python missing (needed for mix/QA helper scripts): winget install --id Python.Python.3.12 -e') }
if (-not $tools.claude.found) { $notes.Add('Claude Code not found; select a compatible local coding client for this workflow.') }
if (-not $tools.unsloth.found) { $warnings.Add('Unsloth Studio command not found; check the desktop installation and its local API.') }
if ($nvGpus.Count -gt 0) { $notes.Add("NVIDIA driver $($nvGpus[0].driver): update to the latest Game Ready or Studio driver before installing models.") }

Write-Section 'Verdict'
foreach ($g in $goods)    { Write-Host ('  [OK]   ' + $g) -ForegroundColor Green }
foreach ($w in $warnings) { Write-Host ('  [FIX]  ' + $w) -ForegroundColor Yellow }
foreach ($n in $notes)    { Write-Host ('  [NOTE] ' + $n) -ForegroundColor Gray }
if ($warnings.Count -eq 0) {
    Write-Host ''
    Write-Host '  No checker warnings. Continue from STATUS.md and handoff.md.' -ForegroundColor Green
}

if ($Json) {
    $report.verdict = [ordered]@{ ok = $goods; fix = $warnings; note = $notes }
    $base = $PSScriptRoot
    if (-not $base) { $base = (Get-Location).Path }
    $outPath = Join-Path $base 'check-film-pc.json'
    try {
        $report | ConvertTo-Json -Depth 6 | Out-File -FilePath $outPath -Encoding utf8
        Write-Host ''
        Write-Host "  Saved $outPath"
    } catch {
        Write-Host "  Could not save JSON: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host '  (This script only reads information. It changed nothing on your PC.)' -ForegroundColor DarkGray
