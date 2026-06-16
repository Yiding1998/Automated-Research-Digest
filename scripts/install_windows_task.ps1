param(
    [string]$TaskName = "Research Digest",
    [string]$ConfigPath = "",
    [string]$At = "08:30",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

if (-not $ConfigPath) {
    $ConfigPath = Join-Path (Resolve-Path ".").Path "config.toml"
}

$ConfigPath = (Resolve-Path $ConfigPath).Path
$Workspace = Split-Path -Parent $ConfigPath
$Command = "cd /d `"$Workspace`" && $Python -m research_digest run --config `"$ConfigPath`""

schtasks /Create /F /SC DAILY /TN $TaskName /TR "cmd.exe /c $Command" /ST $At | Out-Host
Write-Host "Installed daily task '$TaskName' at $At"
