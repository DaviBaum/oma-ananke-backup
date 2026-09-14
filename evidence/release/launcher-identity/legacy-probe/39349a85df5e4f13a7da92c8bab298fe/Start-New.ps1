param([ValidateRange(1, 65535)][int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath (Join-Path $projectRoot 'runtime\python.exe')) {
    $pythonPath = Join-Path $projectRoot 'runtime\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot 'Install-OMA.ps1')
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'ui\dist\index.html'))) {
    throw 'The workbench build is missing. Run Install-OMA.ps1 to build it.'
}
$omaDirectory = Join-Path $projectRoot '.oma'
# Bind both the local probe and the launched service to this package's source,
# independent of a caller's installed oma or inherited frozen PYTHONPATH.
$env:PYTHONPATH = Join-Path $projectRoot 'src'
Remove-Item Env:OMA_EXECUTABLE_BUILD -ErrorAction SilentlyContinue
Remove-Item Env:OMA_CONTROL_RUN_ID -ErrorAction SilentlyContinue
$probe = 'import json,sys; from pathlib import Path; sys.path.insert(0,sys.argv[2]); from oma.build_identity import checker_version; print(json.dumps(dict(checker_version=checker_version(),data_directory=str(Path(sys.argv[1]).resolve()))))'
$expectedJson = & $pythonPath -s -c $probe $omaDirectory (Join-Path $projectRoot 'src')
if ($LASTEXITCODE -ne 0) { throw 'Could not determine this package runtime identity.' }
$expected = $expectedJson | ConvertFrom-Json
if (-not $expected.checker_version -or -not $expected.data_directory) { throw 'Package runtime identity is incomplete.' }
function Assert-OmaServerIdentity($health) {
    $identity = $health.server_identity
    $matches = $health.application -ceq 'oma-ananke' -and $null -ne $identity
    if ($matches) {
        $matches = $identity.schema -ceq 'oma.server-identity/1' -and
            $identity.checker_version -ceq $expected.checker_version -and
            $identity.source_changed -is [bool] -and $identity.source_changed -eq $false -and
            $identity.startup_environment_matches -is [bool] -and $identity.startup_environment_matches -eq $true -and
            [StringComparer]::OrdinalIgnoreCase.Equals([string]$identity.data_directory, [string]$expected.data_directory)
    }
    if (-not $matches) {
        throw "Port $Port serves a different or unidentified OMA build/store. This package will not reuse it. Choose an unused port with -Port; the existing process was not stopped."
    }
}
$logDirectory = Join-Path $omaDirectory 'logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$url = "http://127.0.0.1:$Port"
$running = $false
try {
    $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 3
} catch {
    $health = $null
    # An HTTP response means a server owns this port even if it rejects health.
    if ($_.Exception.Response -or $_.Exception.Status -ne [System.Net.WebExceptionStatus]::ConnectFailure) {
        throw "Port $Port is occupied or its server identity could not be established. Choose an unused port with -Port; the existing process was not stopped."
    }
}
if ($null -ne $health) {
    Assert-OmaServerIdentity $health
    $running = $true
}
if (-not $running) {
    $arguments = @('-m', 'oma.cli', 'serve', '--port', "$Port", '--data-dir', ('"' + $omaDirectory + '"'))
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'service.out.log') -RedirectStandardError (Join-Path $logDirectory 'service.err.log')
    @{ pid = $process.Id; port = $Port; started = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $omaDirectory 'service.json') -Encoding utf8
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 1
        } catch { $health = $null }
        if ($null -ne $health) {
            Assert-OmaServerIdentity $health
            $running = $true
            break
        }
        if ($process.HasExited) { throw "Local engine stopped. See $logDirectory\service.err.log" }
    }
    if (-not $running) { throw "Engine did not become ready. See $logDirectory\service.err.log" }
}
Write-Host "OMA + ANANKE is available at $url"
if (-not $NoBrowser) { Start-Process $url }
