<#
.SYNOPSIS
  Полный прогон учебного комплекта на Windows-ВМ с MS Project.

.DESCRIPTION
  Последовательно: сборка документов → XML→.mpp → скриншоты → сверка →
  отчёты со скриншотами → папка сдачи → checksums → git.

  По умолчанию XML не пересобирается: на ВМ достаточно закоммиченных
  out/*.xml, а Java для MPXJ не нужна. Для пересборки XML добавьте -Xml.

  Падение шага прерывает прогон. Расхождения verify — это расхождения
  данных, а не сбой исполнения: по умолчанию они дают предупреждение,
  с -Strict — ошибку. Истина — MS Project; расхождения объясняются в
  automation/results/NOTES.md, а не подгоняются.

.PARAMETER NoGit
  Выполнить всё, но не коммитить.

.PARAMETER Strict
  Считать расхождения verify ошибкой.

.PARAMETER KillStale
  Завершить оставшиеся WINPROJ.exe перед стартом.

.PARAMETER Xml
  Пересобрать out/*.xml (нужна Java 8+).

.PARAMETER SkipBuild
  Не пересобирать документы, использовать текущие out/.

.PARAMETER TimeoutMinutes
  Watchdog на шаг; по умолчанию 20 минут.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File vm\run_all.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File vm\run_all.ps1 -Xml -KillStale
#>
[CmdletBinding()]
param(
    [switch]$NoGit,
    [switch]$Strict,
    [switch]$KillStale,
    [switch]$Xml,
    [switch]$SkipBuild,
    [int]$TimeoutMinutes = 20,
    [string]$Python = "py"
)

$ErrorActionPreference = 'Stop'
$vm = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $vm '..')).Path
Set-Location $repo

# --- висячий WINPROJ от прошлого прогона ------------------------------------
$stale = @(Get-Process -Name WINPROJ -ErrorAction SilentlyContinue)
if ($stale.Count -gt 0) {
    if ($KillStale) {
        Write-Host "найдены висячие MS Project — завершаю (-KillStale):" -ForegroundColor Yellow
        $stale | ForEach-Object { Write-Host ("  PID {0}: {1}" -f $_.Id, $_.MainWindowTitle) -ForegroundColor Yellow }
        $stale | ForEach-Object { $_.Kill() }
        Start-Sleep -Seconds 3
    } else {
        $stale | ForEach-Object { Write-Host ("  PID {0}: {1}" -f $_.Id, $_.MainWindowTitle) -ForegroundColor Red }
        throw ("найден запущенный MS Project (PID " + ($stale.Id -join ', ') + "). " +
               "Закройте его вручную или перезапустите с -KillStale.")
    }
}

$log = @()
function Invoke-Step {
    param(
        [string]$Name,
        [string]$File,
        [string[]]$CmdArgs = @(),
        [switch]$AllowFail
    )
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    $cmd = @($File) + $CmdArgs
    Write-Host ("    " + $Python + " " + ($cmd -join ' ')) -ForegroundColor DarkGray

    $pyExe = if ($Python -eq 'py') { (Get-Command py).Source } else { $Python }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pyExe
    $psi.Arguments = ($cmd | ForEach-Object { '"' + $_.Replace('"', '""') + '"' }) -join ' '
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    $script:proc = $proc
    $null = $proc.Start()
    $done = $proc.WaitForExit([int]($TimeoutMinutes * 60) * 1000)
    if (-not $done) {
        $proc.Kill(); $proc.WaitForExit()
        @(Get-Process -Name WINPROJ -ErrorAction SilentlyContinue) | ForEach-Object { $_.Kill() }
        $script:log += [pscustomobject]@{ step = $Name; exit = -1; watchdog = $true }
        throw "шаг '$Name' завис дольше $TimeoutMinutes мин (watchdog)"
    }
    $out = $proc.StandardOutput.ReadToEnd()
    $err = $proc.StandardError.ReadToEnd()
    if ($out) { Write-Host $out.TrimEnd() }
    if ($err) { Write-Host $err.TrimEnd() -ForegroundColor Red }
    $code = $proc.ExitCode
    $script:proc = $null
    $script:log += [pscustomobject]@{ step = $Name; exit = $code }
    if ($code -ne 0) {
        if ($AllowFail) {
            Write-Host ("предупреждение: шаг '{0}' вернул {1}; это расхождение данных, не сбой" -f $Name, $code) -ForegroundColor Yellow
            return
        }
        throw "шаг '$Name' завершился с кодом $code — прерываю прогон"
    }
}

Write-Host "Учебный комплект: ЛР1–9 + СРС (SIW) + ДЗ 10/12" -ForegroundColor Green
Write-Host "репозиторий: $repo"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

if (-not $SkipBuild) {
    Invoke-Step 'build' 'build_all.py' $(if ($Xml) { @('--xml') } else { @() })
}

# XML → .mpp. Java не нужна: scripts/xml_to_mpp.py только открывает готовые XML.
Invoke-Step 'mpp' 'scripts/xml_to_mpp.py'

# 22 снимка ЛР; СРС-снимки снимаются отдельно, если для них есть шаги.
Invoke-Step 'shots' '-m' @('automation.ms_project_ui', 'shots')

# Сверка с MS Project: расхождения данных — предупреждение, не abort.
Invoke-Step 'verify' 'vm/verify.py' @() -AllowFail:(-not $Strict)

# Готовые отчёты: лабораторный и СРС (SIW).
Invoke-Step 'report' '-m' @(
    'automation.fill_report',
    '--src', 'out/ms-project-labs-report.docx',
    '--dst', 'automation/results/ms-project-labs-report-final.docx'
)
Invoke-Step 'siw-report' '-m' @(
    'automation.fill_report',
    '--src', 'out/siw-report.docx',
    '--dst', 'automation/results/siw-report-final.docx'
)

Invoke-Step 'submit' 'vm/make_submission.py'
Invoke-Step 'checksums' 'vm/hash_artifacts.py'

if ($NoGit) {
    Write-Host ""
    Write-Host "-NoGit: результаты не закоммичены" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "==> git" -ForegroundColor Cyan
    git add -- out siw docs/guidelines docs/artifacts src tests vm scripts build.py build_siw.py build_infosec.py build_guidelines.py build_artifacts.py build_all.py
    $pending = git status --porcelain -- out siw docs/guidelines docs/artifacts src tests vm scripts
    if ($pending) {
        git commit -m ("chore(pm): full course build " + [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm'))
        git log --oneline -1
    } else {
        Write-Host "    изменений нет — коммит не нужен" -ForegroundColor DarkGray
    }
}

$left = @(Get-Process -Name WINPROJ -ErrorAction SilentlyContinue)
if ($left.Count -gt 0) {
    $left | ForEach-Object { Write-Host ("  УТЁК: PID {0}: {1}" -f $_.Id, $_.MainWindowTitle) -ForegroundColor Red }
    Write-Host "предупреждение: после прогона остались процессы MS Project — проверь MSP.quit()" -ForegroundColor Yellow
}

$sw.Stop()
Write-Host ""
Write-Host ("готово за {0} мин" -f [math]::Round($sw.Elapsed.TotalMinutes, 1)) -ForegroundColor Green
$log | Format-Table -AutoSize

