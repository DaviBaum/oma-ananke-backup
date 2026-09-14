$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
$started = [DateTime]::UtcNow.ToString('o')
$receipt = Join-Path $PSScriptRoot 'exit.json'
Set-Location -LiteralPath $workspace
try {
    & (Join-Path $workspace '.venv/Scripts/python.exe') 'scripts/native_validate_checkpoint.py' '--source-checkpoint' '4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef' '--source-directory' '.oma/development/passive-native-tree/runtimes/4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef/src' '--test-snapshot-record' 'evidence/release/passive-tree-full-32b35337603643cb8cb3020033472fed/result.json'
    $returnCode = $LASTEXITCODE
    [ordered]@{status='WRAPPER_EXIT_OBSERVED'; exit_code=$returnCode; started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o'); prior_attempt='4044a58d5639-c1bf1c7de425'; tests_restarted_after_incomplete_attempt=$true} | ConvertTo-Json | Set-Content -LiteralPath $receipt
    exit $returnCode
} catch {
    [ordered]@{status='WRAPPER_FAILED'; error=$_.ToString(); started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath $receipt
    throw
}
