# Rotates the backend admin key used by n8n credential "TNAA Backend Admin" (id TnaaAdminKeyCred, Header Auth
# X-Admin-Key). Run ONLY when approved, before or during ADMIN_API_KEY activation; never prints the secret.
#
#  1. Generates 32 random bytes (base64url, 43 chars) and stores them with Windows DPAPI (current user) in
#     $SecretPath; the previous file is kept as <name>.retired-<UTC>.dpapi next to it.
#  2. Overwrites the credential in the n8n container through `n8n import:credentials --input=/dev/stdin`:
#     the plaintext only travels through process stdin and is never written to a file, argument or log.
#  3. The backend picks the new value up only after deploy/Set-AdminApiKeyEnv.ps1 and a backend recreate.
#     Until then (ADMIN_API_KEY unset) the admin endpoints stay disabled (HTTP 403) whatever the credential holds.
param(
    [string]$Container = 'tunisian-admin-assistant-n8n-1',
    [string]$ProjectId = 'e8jabjrbSWw1NMoA',
    [string]$SecretPath = (Join-Path $env:USERPROFILE '.tnaa-private\admin-api-key.dpapi')
)
$ErrorActionPreference = 'Stop'
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$secret = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
[Array]::Clear($bytes, 0, $bytes.Length)

if (Test-Path -LiteralPath $SecretPath) {
    $retired = $SecretPath -replace '\.dpapi$', ('.retired-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '.dpapi')
    Copy-Item -LiteralPath $SecretPath -Destination $retired
    "previous secret kept (DPAPI) as $(Split-Path $retired -Leaf)"
}
$ss = ConvertTo-SecureString $secret -AsPlainText -Force
Set-Content -LiteralPath $SecretPath -Value (ConvertFrom-SecureString $ss) -Encoding ASCII -NoNewline
$ss.Dispose()

$cred = '[{"id":"TnaaAdminKeyCred","name":"TNAA Backend Admin","type":"httpHeaderAuth","data":{"name":"X-Admin-Key","value":"' + $secret + '"}}]'
$secret = $null
$prevEnc = [Console]::InputEncoding
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'docker'; $psi.UseShellExecute = $false
    $psi.Arguments = "exec -i -e N8N_RUNNERS_BROKER_PORT=5690 $Container n8n import:credentials --input=/dev/stdin --projectId=$ProjectId"
    $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    $b = [Text.Encoding]::UTF8.GetBytes($cred); $cred = $null
    $p.StandardInput.BaseStream.Write($b, 0, $b.Length); $p.StandardInput.Close(); [Array]::Clear($b, 0, $b.Length)
    $out = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd(); $p.WaitForExit()
    "n8n import:credentials exit=$($p.ExitCode): " + (($out -split "`n" | ? { $_ -match 'Successfully|Error|error' }) -join ' ')
    if ($p.ExitCode -ne 0) { throw 'credential import failed: the DPAPI file holds the NEW secret, n8n still the old one; rerun this script' }
} finally {
    [Console]::InputEncoding = $prevEnc
}
"rotation done in n8n; next (approved deployment only): deploy/Set-AdminApiKeyEnv.ps1, then recreate the backend"
