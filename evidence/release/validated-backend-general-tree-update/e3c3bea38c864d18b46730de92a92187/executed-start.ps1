$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$pointer = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'latest-preflight.json') -Raw | ConvertFrom-Json
$evidence = $pointer.directory
$shutdown = Get-Content -LiteralPath (Join-Path $evidence 'shutdown-complete.json') -Raw | ConvertFrom-Json
if ($shutdown.status -ne 'GRACEFUL_OWNED_SHUTDOWN_COMPLETED') { throw 'Old owned server must have stopped cleanly' }
if (Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue) { throw 'Port remains owned' }
$prepared = Get-Content -LiteralPath (Join-Path $evidence 'prepared-start.json') -Raw | ConvertFrom-Json
$expected = Get-Content -LiteralPath (Join-Path $evidence 'live-expected-source.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $evidence 'prepared-launcher.py') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $prepared.launcher_sha256) { throw 'Launcher changed' }
if ((Get-FileHash -LiteralPath (Join-Path $evidence 'live-expected-source.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $prepared.manifest_sha256) { throw 'Manifest changed' }
Copy-Item -LiteralPath (Join-Path $evidence 'prepared-launcher.py') -Destination (Join-Path $workspace '.oma/start_validated_backend.py')
$env:PYTHONPATH = $expected.source_directory
$env:OMA_EXECUTABLE_BUILD = $expected.checker_version
$stdout = Join-Path $evidence 'new-backend.stdout.log'
$stderr = Join-Path $evidence 'new-backend.stderr.log'
$process = Start-Process -FilePath (Join-Path $workspace '.venv/Scripts/python.exe') -ArgumentList ('"' + (Join-Path $workspace '.oma/start_validated_backend.py') + '"') -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
[ordered]@{port=8768;pythonpath=$expected.source_directory;pid=$process.Id;started_utc=$process.StartTime.ToUniversalTime().ToString('o');executable_build=$expected.checker_version;recovery_enabled=$false;expected_source_manifest=(Join-Path $evidence 'live-expected-source.json');stdout=$stdout;stderr=$stderr;launcher_sha256=$prepared.launcher_sha256;data_directory=(Join-Path $workspace '.oma')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $workspace '.oma/service.validated.json')
Copy-Item -LiteralPath $PSCommandPath -Destination (Join-Path $evidence 'executed-start.ps1')
Write-Output ('STARTED_OWNED_VALIDATED_EDF_LAUNCHER=' + $process.Id)
