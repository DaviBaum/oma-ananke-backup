param([Parameter(Mandatory=$true)][string]$SnapshotRecord)
$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$started = [DateTime]::UtcNow.ToString('o')
$preparation = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'preparation.json') -Raw | ConvertFrom-Json
$declaration = Get-Content -LiteralPath $SnapshotRecord -Raw | ConvertFrom-Json
if ($declaration.checker_version -ne ('oma-independent-checker/2:' + $preparation.source_checkpoint)) { throw 'Wrong full-suite source declaration' }
if ($declaration.test_node_count -ne $preparation.expected_full_test_nodes) { throw 'Not the exact full-suite node declaration' }
if (($declaration.snapshot_files.PSObject.Properties | Measure-Object).Count -ne $preparation.expected_test_input_count) { throw 'Wrong full input count' }
$expectedInputs = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'snapshot-files.json') -Raw | ConvertFrom-Json
foreach ($entry in $expectedInputs.PSObject.Properties) {
    if ($declaration.snapshot_files.($entry.Name) -cne $entry.Value) { throw ('Input identity changed: ' + $entry.Name) }
}
foreach ($entry in $preparation.driver_source_files.PSObject.Properties) {
    $driver = Join-Path $workspace ('scripts/' + $entry.Name)
    if ((Get-FileHash -LiteralPath $driver -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value) { throw ('Driver changed: ' + $entry.Name) }
}
Copy-Item -LiteralPath $SnapshotRecord -Destination (Join-Path $PSScriptRoot 'root-full-declaration-at-launch.json')
[ordered]@{status='STARTING_EXACT_DECLARED_FULL_SUITE'; started_utc=$started; source_checkpoint=$preparation.source_checkpoint; snapshot_record=(Resolve-Path -LiteralPath $SnapshotRecord).Path; snapshot_record_sha256=(Get-FileHash -LiteralPath $SnapshotRecord -Algorithm SHA256).Hash.ToLowerInvariant(); wrapper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant(); test_node_count=$declaration.test_node_count} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'launch-provenance.json')
Set-Location -LiteralPath $workspace
try {
    & (Join-Path $workspace '.venv/Scripts/python.exe') 'scripts/native_validate_checkpoint.py' '--source-checkpoint' $preparation.source_checkpoint '--source-directory' $preparation.source_directory '--test-snapshot-record' $SnapshotRecord
    $returnCode = $LASTEXITCODE
    [ordered]@{status='WRAPPER_EXIT_OBSERVED'; exit_code=$returnCode; started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'exit.json')
    exit $returnCode
} catch {
    [ordered]@{status='WRAPPER_FAILED'; error=$_.ToString(); started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'exit.json')
    throw
}
