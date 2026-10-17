# Start the local demonstration interface (proxy to the real n8n workflow 03) on http://127.0.0.1:8090
# Usage (from the repository root):  powershell -ExecutionPolicy Bypass -File scripts\start_demo_ui.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# Free port 8090 if a previous demo interface is still running (only that port).
Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

Write-Output "Checking services..."
foreach ($u in @("http://127.0.0.1:5678/healthz", "http://127.0.0.1:8000/health")) {
    try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 $u; Write-Output "  $u -> HTTP $($r.StatusCode)" }
    catch { Write-Output "  $u -> UNAVAILABLE (see docs/DEMO_FALLBACK.md, section 'Emergency recovery')" }
}
Write-Output "Demo interface: http://127.0.0.1:8090  (Ctrl+C to stop)"
& .venv\Scripts\python.exe -m uvicorn demo_ui.app:app --host 127.0.0.1 --port 8090
