param([Parameter(Mandatory=$true)][string]$Result,[Parameter(Mandatory=$true)][string]$Preparation,[Parameter(Mandatory=$true)][ValidateSet('suite','cases')][string]$Mode)
$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$started = [DateTime]::UtcNow.ToString('o')
$data = Get-Content -LiteralPath (Join-Path $Preparation 'preparation.json') -Raw | ConvertFrom-Json
foreach ($entry in $data.driver_sources.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $workspace $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value) { throw ('Driver changed: ' + $entry.Name) }
}
$portable = Get-Content -LiteralPath $Result -Raw | ConvertFrom-Json
if ($portable.status -cne 'ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS') { throw 'Incomplete package build' }
if ($portable.source_checkpoint -cne $data.source_checkpoint) { throw 'Wrong source checkpoint' }
$plan = Get-Content -LiteralPath (Join-Path $Preparation 'real-model-inputs.json') -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath (Join-Path $Preparation 'real-model-inputs.json') -Algorithm SHA256).Hash.ToLowerInvariant() -cne $portable.real_model_validation_inputs_sha256) { throw 'Declaration changed' }
Set-Location -LiteralPath $workspace
$python = Join-Path $workspace '.venv/Scripts/python.exe'
$env:PYTHONPATH = Join-Path $portable.package 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONNOUSERSITE = '1'
try {
    if ($Mode -eq 'suite') {
        & $python 'scripts/native_portable_full_suite.py' '--result' $Result
        if ($LASTEXITCODE -ne 0) { throw ('Bundled suite exited ' + $LASTEXITCODE) }
    } else {
        & $python 'scripts/native_portable_guard_probe.py' '--result' $Result
        if ($LASTEXITCODE -ne 0) { throw ('Network denial probe exited ' + $LASTEXITCODE) }
        foreach ($role in $plan.roles.PSObject.Properties) {
            $target = $role.Value
            & $python 'scripts/native_real_model_validation.py' '--portable-validation' $Result '--source-checkpoint' $data.source_checkpoint '--candidate-id' $target.candidate_id '--original-store' $target.original_store '--expected-export-sha256' $target.expected_export_sha256 '--prior-checker-version' $target.prior_checker_version '--validation-role' $role.Name '--output-directory' (Split-Path -Parent $Result)
            if ($LASTEXITCODE -ne 0) { throw ('Real validation ' + $role.Name + ' exited ' + $LASTEXITCODE) }
        }
    }
    [ordered]@{status='WRAPPER_EXIT_OBSERVED';exit_code=0;mode=$Mode;portable_result=$Result;portable_result_sha256=(Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash.ToLowerInvariant();started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation ($Mode+'-exit.json'))
} catch {
    [ordered]@{status='WRAPPER_FAILED';error=$_.ToString();mode=$Mode;started_utc=$started;completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Preparation ($Mode+'-exit.json'))
    throw
}
