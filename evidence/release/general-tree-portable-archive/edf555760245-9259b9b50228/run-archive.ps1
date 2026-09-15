$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Davi\Downloads\oma'
Set-Location -LiteralPath $workspace
$started = [DateTime]::UtcNow.ToString('o')
try {
  & (Join-Path $workspace '.venv/Scripts/python.exe') '.oma/development/general-tree-portable/archive.py'
  $code = $LASTEXITCODE
  [ordered]@{status='WRAPPER_EXIT_OBSERVED'; exit_code=$code; started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'archive-exit.json')
  exit $code
} catch {
  [ordered]@{status='WRAPPER_FAILED'; error=$_.ToString(); started_utc=$started; completed_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'archive-exit.json')
  throw
}
