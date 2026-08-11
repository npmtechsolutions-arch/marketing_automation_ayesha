# PowerShell script to stop both Backend and Frontend servers
Write-Host "Stopping Marketing Automation Servers..." -ForegroundColor Yellow

function Kill-ProcessAndChildren ($targetPid) {
    # 1. Kill any child processes first
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $targetPid" -ErrorAction SilentlyContinue
    if ($children) {
        foreach ($child in $children) {
            Kill-ProcessAndChildren $child.ProcessId
        }
    }
    # 2. Kill the target process itself
    Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue
}

$ports = @(8000, 5173)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($targetPid in $pids) {
            Write-Host "Killing process $targetPid and its child processes listening on port $port..." -ForegroundColor Cyan
            Kill-ProcessAndChildren $targetPid
        }
    }
}

Write-Host "All servers stopped successfully!" -ForegroundColor Green
