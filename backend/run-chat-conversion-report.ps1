param(
    [string]$Date,
    [int]$LastDays = 1,
    [string]$LogFile = "chat-events.log",
    [string]$OutputDir = "reports"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $scriptDir ".venv\Scripts\python.exe"
$analyzer = Join-Path $scriptDir "analyze_chat_conversions.py"
$logPath = Join-Path $scriptDir $LogFile
$reportDir = Join-Path $scriptDir $OutputDir

if (-not (Test-Path $pythonExe)) {
    throw "Python executable not found: $pythonExe"
}

if (-not (Test-Path $analyzer)) {
    throw "Analyzer script not found: $analyzer"
}

if (-not (Test-Path $logPath)) {
    throw "Log file not found: $logPath"
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

if ($Date) {
    $stamp = $Date
    $dateArgs = @("--date", $Date)
} else {
    if ($LastDays -le 0) {
        throw "LastDays must be greater than 0."
    }
    $stamp = (Get-Date).ToString("yyyy-MM-dd")
    $dateArgs = @("--last-days", "$LastDays")
}

$csvPath = Join-Path $reportDir "chat-conversion-report-$stamp.csv"
$mdPath = Join-Path $reportDir "chat-conversion-report-$stamp.md"

& $pythonExe $analyzer $logPath @dateArgs --csv $csvPath --md $mdPath
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    throw "Report generation failed."
}

Write-Host ""
Write-Host "Reports generated:"
Write-Host "  CSV: $csvPath"
Write-Host "  MD : $mdPath"
