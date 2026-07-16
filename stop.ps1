# PowerShell script to stop both Backend and Frontend servers
Write-Host "Stopping Marketing Automation Servers..." -ForegroundColor Yellow

$ports = @(8000, 5173)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($targetPid in $pids) {
            Write-Host "Killing process $targetPid listening on port $port..." -ForegroundColor Cyan
            Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "All servers stopped successfully!" -ForegroundColor Green
