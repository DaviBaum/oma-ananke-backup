param([Parameter(Mandatory=$true)][string]$Result,[Parameter(Mandatory=$true)][string]$Preparation)
$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$started = [DateTime]::UtcNow.ToString('o')
$data = Get-Content -LiteralPath (Join-Path $Preparation 'preparation.json') -Raw | ConvertFrom-Json
foreach ($entry in $data.driver_sources.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $workspace $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value) { throw ('Driver changed: ' + $entry.Name) }
}
foreach ($mode in @('suite','cases')) {
    $completion = Get-Content -LiteralPath (Join-Path $Preparation ($mode+'-exit.json')) -Raw | ConvertFrom-Json
    if ($completion.status -cne 'WRAPPER_EXIT_OBSERVED' -or $completion.exit_code -ne 0) { throw ('Incomplete '+$mode) }
}
$portable = Get-Content -LiteralPath $Result -Raw | ConvertFrom-Json
$env:PYTHONPATH = Join-Path $portable.package 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONNOUSERSITE = '1'
Set-Location -LiteralPath $workspace
try {
    & (Join-Path $workspace '.venv/Scripts/python.exe') 'scripts/native_seal_portable.py' '--result' $Result
    if ($LASTEXITCODE -ne 0) { throw ('Seal exited ' + $LASTEXITCODE) }
    [ordered]@{status='WRAPPER_EXIT_OBSERVED';exit_code=0;portable_result=$Result;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation 'seal-exit.json')
} catch {
    [ordered]@{status='WRAPPER_FAILED';error=$_.ToString();started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation 'seal-exit.json')
    throw
}
