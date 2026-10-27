# Snapshot of the Windows/MS Project environment without PII.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File vm\collect_env.ps1
# Output:
#   automation/results/windows-env-pins.txt
#
# The script never writes user names, computer names, IP addresses, tokens or
# account identifiers: only versions and feature flags.

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outDir = Join-Path $root 'automation\results'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir 'windows-env-pins.txt'

function Get-RegValue([string]$Path, [string]$Name) {
    try {
        (Get-ItemProperty -Path $Path -Name $Name -ErrorAction Stop).$Name
    } catch {
        $null
    }
}

$os = Get-CimInstance Win32_OperatingSystem
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('captured_utc: ' + [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))
$lines.Add('os_caption: ' + $os.Caption)
$lines.Add('os_version: ' + $os.Version)
$lines.Add('os_build: ' + $os.BuildNumber)
$lines.Add('os_arch: ' + $os.OSArchitecture)
$lines.Add('powershell: ' + $PSVersionTable.PSVersion.ToString())

$projectExe = Get-Command WINPROJ.EXE -ErrorAction SilentlyContinue
if ($projectExe) {
    $lines.Add('winproj_path: ' + $projectExe.Source)
    $lines.Add('winproj_version: ' + $projectExe.Version)
} else {
    $lines.Add('winproj_path: not found')
}
$lines.Add('project_click_to_run: ' + (Get-RegValue 'HKCU:\Software\Microsoft\Office\16.0\Common\General' 'ClickedToRun'))
$lines.Add('office_build: ' + (Get-RegValue 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration' 'VersionToReport'))

try { $lines.Add('python_launcher: ' + ((py --version) -join ' ')) } catch { $lines.Add('python_launcher: not found') }
try { $lines.Add('python: ' + ((py -c "import sys; print(sys.version.split()[0])") -join ' ')) } catch { $lines.Add('python: not found') }
try { $lines.Add('java: ' + ((java -version 2>&1) -join ' ')) } catch { $lines.Add('java: not found') }

foreach ($pkg in @('pywin32', 'pywinauto', 'psutil', 'pillow', 'python-docx', 'mpxj', 'JPype1')) {
    try {
        $ver = (py -m pip show $pkg 2>$null | Select-String '^Version:' | Select-Object -First 1).Line
        if ($ver) { $lines.Add("pip_${pkg}: " + ($ver -replace '^Version:\s*', '')) }
        else { $lines.Add("pip_${pkg}: not installed") }
    } catch {
        $lines.Add("pip_${pkg}: not installed")
    }
}

$lines.Add('notes: no usernames, hostnames, IP addresses or tokens are collected')
Set-Content -Path $out -Value $lines -Encoding UTF8
Write-Host "written: $out"

