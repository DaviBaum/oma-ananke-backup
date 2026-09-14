param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & (Join-Path $projectRoot 'Install-OMA.ps1')
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'ui\dist\index.html'))) {
    throw 'The workbench build is missing. Run Install-OMA.ps1 to build it.'
}
$omaDirectory = Join-Path $projectRoot '.oma'
$logDirectory = Join-Path $omaDirectory 'logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$url = "http://127.0.0.1:$Port"
$running = $false
try {
    $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 3
    $running = $health.application -eq 'oma-ananke'
    if (-not $running) { throw "Port $Port belongs to another service." }
} catch {
    if ($_.Exception.Message -like '*belongs to another*') { throw }
}
if (-not $running) {
    $arguments = @('-m', 'oma.cli', 'serve', '--port', "$Port", '--data-dir', ('"' + $omaDirectory + '"'))
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDirectory 'service.out.log') -RedirectStandardError (Join-Path $logDirectory 'service.err.log')
    @{ pid = $process.Id; port = $Port; started = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $omaDirectory 'service.json') -Encoding utf8
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 250
        try {
            $health = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 1
            if ($health.application -eq 'oma-ananke') { $running = $true; break }
        } catch { }
        if ($process.HasExited) { throw "Local engine stopped. See $logDirectory\service.err.log" }
    }
    if (-not $running) { throw "Engine did not become ready. See $logDirectory\service.err.log" }
}
Write-Host "OMA + ANANKE is available at $url"
if (-not $NoBrowser) { Start-Process $url }
