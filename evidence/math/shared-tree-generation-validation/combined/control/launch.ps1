param([ValidateSet('focused','full')][string]$Phase='focused')
$validationStage = $PSScriptRoot
$validationRoot = (Resolve-Path -LiteralPath (Join-Path $validationStage '..\..\..')).Path
$validationPython = (Resolve-Path -LiteralPath (Join-Path $validationRoot '.venv\Scripts\python.exe')).Path
$validationRunner = Join-Path $validationStage 'run_validation.py'
$validationArgs = @('"' + $validationRunner + '"', $Phase)
$validationProcess = Start-Process -FilePath $validationPython -ArgumentList $validationArgs -WorkingDirectory $validationStage -WindowStyle Hidden -RedirectStandardOutput (Join-Path $validationStage ($Phase + '-launch.stdout.log')) -RedirectStandardError (Join-Path $validationStage ($Phase + '-launch.stderr.log')) -PassThru
$validationReceipt = @{
    phase=$Phase
    launch_pid=$validationProcess.Id
    runner=$validationRunner
    interpreter=$validationPython
    script_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $PSCommandPath).Hash.ToLowerInvariant()
    launched_utc=[DateTime]::UtcNow.ToString('o')
    window_style='Hidden'
}
$validationReceipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $validationStage ($Phase + '-launch.json')) -Encoding utf8
$validationReceipt | ConvertTo-Json
