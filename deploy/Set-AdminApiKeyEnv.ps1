# Sets ADMIN_API_KEY in the git-ignored .env from the DPAPI-protected secret created on 2026-10-18 (the same value as
# the n8n credential "TNAA Backend Admin" / X-Admin-Key). Run ONLY during an approved backend deployment, then
# recreate the backend: docker compose up -d --no-deps --no-build --pull never backend
# The secret is never printed. A timestamped copy of the previous .env is kept OUTSIDE the repository
# (%USERPROFILE%\tna-backups\env), because only `.env` itself is git-ignored.
param([string]$EnvFile = (Join-Path (Split-Path $PSScriptRoot -Parent) '.env'))
$ErrorActionPreference = 'Stop'
$keyPath = Join-Path $env:USERPROFILE '.tnaa-private\admin-api-key.dpapi'
if (-not (Test-Path -LiteralPath $keyPath)) { throw "Stored admin secret not found: $keyPath" }
if (-not (Test-Path -LiteralPath $EnvFile)) { throw ".env not found: $EnvFile" }
$backupDir = Join-Path $env:USERPROFILE 'tna-backups\env'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backup = Join-Path $backupDir ('env.before-admin-key-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
Copy-Item -LiteralPath $EnvFile -Destination $backup
$secure = ConvertTo-SecureString ((Get-Content -Raw -LiteralPath $keyPath).Trim())
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    $lines = [IO.File]::ReadAllLines($EnvFile)
    $found = $false
    $out = foreach ($l in $lines) { if ($l -match '^ADMIN_API_KEY=') { $found = $true; "ADMIN_API_KEY=$value" } else { $l } }
    if (-not $found) { $out = @($out) + "ADMIN_API_KEY=$value" }
    [IO.File]::WriteAllLines($EnvFile, [string[]]$out, (New-Object System.Text.UTF8Encoding($false)))
    "ADMIN_API_KEY written to .env (value not shown); previous .env saved as $backup"
} finally {
    $value = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $secure.Dispose()
}
