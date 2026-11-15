# Starts TopRanker on Windows when Docker Engine runs inside WSL2 (no Docker Desktop).
#   powershell -ExecutionPolicy Bypass -File scripts\start_windows.ps1
# WSL stops a distribution shortly after its last session ends, which would stop the
# containers too, so this keeps one hidden session open until you log off.
param([string]$Distro = "Ubuntu")

$repo = (Resolve-Path "$PSScriptRoot\..").Path
$mount = "/mnt/" + $repo.Substring(0, 1).ToLower() + ($repo.Substring(2) -replace "\\", "/")

if (-not (Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" |
          Where-Object { $_.CommandLine -match "sleep infinity" })) {
    Start-Process wsl -ArgumentList "-d", $Distro, "-u", "root", "--", "sleep", "infinity" -WindowStyle Hidden
    Start-Sleep 5
}
wsl -d $Distro -u root --cd $mount -- docker compose up -d --wait
Write-Host "App: http://localhost:3000    API docs: http://localhost:8000/docs"
