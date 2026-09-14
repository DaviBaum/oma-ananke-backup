param([switch]$Offline)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'runtime\python.exe')) {
    $pythonPath = Join-Path $PSScriptRoot 'runtime\python.exe'
    & $pythonPath -m oma.cli doctor --save evidence/hardware/install.json
    if ($LASTEXITCODE -ne 0) { throw 'Bundled runtime integrity check failed.' }
    Write-Host 'Bundled offline runtime is ready. Open OMA.cmd to start.'
    return
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Install the official Windows x64 Python 3.12 distribution.' }
}
if ($Offline) {
    $wheels = Join-Path $PSScriptRoot 'wheelhouse'
    if (-not (Test-Path -LiteralPath $wheels)) { throw 'Offline installation requires the prepared wheelhouse folder.' }
    & $pythonPath -m pip install --no-index --find-links $wheels -r requirements-runtime.lock
} else {
    & $pythonPath -m pip install -r requirements-runtime.lock
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; inspect the pip error above.' }
& $pythonPath -m pip install -e . --no-deps --no-build-isolation
if ($LASTEXITCODE -ne 0) { throw 'Local application installation failed.' }
if (-not (Test-Path -LiteralPath 'ui\dist\index.html')) {
    if ($Offline) { throw 'Offline package must include the prebuilt ui/dist workbench.' }
    Push-Location -LiteralPath ui
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
& $pythonPath -m oma.cli doctor --save evidence/hardware/install.json
Write-Host 'Installation complete. Open OMA.cmd to start the local workbench.'
