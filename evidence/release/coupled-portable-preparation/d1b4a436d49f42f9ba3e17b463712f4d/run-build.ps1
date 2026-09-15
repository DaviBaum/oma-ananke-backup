param([Parameter(Mandatory=$true)][string]$Preparation)
$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$started = [DateTime]::UtcNow.ToString('o')
$data = Get-Content -LiteralPath (Join-Path $Preparation 'preparation.json') -Raw | ConvertFrom-Json
foreach ($entry in $data.driver_sources.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $workspace $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value) { throw ('Driver changed: ' + $entry.Name) }
}
Set-Location -LiteralPath $workspace
try {
    & (Join-Path $workspace '.venv/Scripts/python.exe') 'scripts/native_portable_candidate.py' '--checkpoint-validation' $data.checkpoint_validation '--real-model-inputs' (Join-Path $Preparation 'real-model-inputs.json')
    $returnCode = $LASTEXITCODE
    [ordered]@{status='WRAPPER_EXIT_OBSERVED';exit_code=$returnCode;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation 'build-exit.json')
    exit $returnCode
} catch {
    [ordered]@{status='WRAPPER_FAILED';error=$_.ToString();started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation 'build-exit.json')
    throw
}
