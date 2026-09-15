$ErrorActionPreference = 'Stop'
$backendManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
$backendRegression = Get-Content -LiteralPath $backendManifest.regression_result -Raw | ConvertFrom-Json
if ($backendRegression.status -ne 'PASS') { throw 'Full regression has not passed; refusing startup' }
if (Get-NetTCPConnection -LocalPort 8769 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8769 is already in use' }
$backendLauncher = Join-Path $PSScriptRoot 'launch_backend.py'
$backendProcess = Start-Process -FilePath $backendManifest.native_environment.interpreter -ArgumentList @('-B', ('"' + $backendLauncher + '"')) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'server.stdout.log') -RedirectStandardError (Join-Path $PSScriptRoot 'server.stderr.log') -PassThru
[ordered]@{
    status = 'PROCESS_STARTED_AFTER_FULL_REGRESSION_PASS'
    launcher_process_id = $backendProcess.Id
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    interpreter = $backendManifest.native_environment.interpreter
    launcher = $backendLauncher
    host = '127.0.0.1'
    port = 8769
    window_style = 'Hidden'
    regression_result = $backendManifest.regression_result
    regression_result_sha256 = (Get-FileHash -LiteralPath $backendManifest.regression_result -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'process-start.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $PSScriptRoot 'process-start.json')
