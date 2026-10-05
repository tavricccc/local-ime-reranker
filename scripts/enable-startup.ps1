#requires -Version 7.0
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPwsh = (Get-Process -Id $PID).Path
$taskCommand = '"' + $taskPwsh + '" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'start-windows.ps1') + '"'
New-ItemProperty -Path 'HKCU:/Software/Microsoft/Windows/CurrentVersion/Run' -Name LocalImeReranker -Value $taskCommand -PropertyType String -Force | Out-Null
