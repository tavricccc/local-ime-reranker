#requires -Version 7.0
$taskPwsh = (Get-Process -Id $PID).Path
$taskPrograms = [Environment]::GetFolderPath('Programs')
$taskShell = New-Object -ComObject WScript.Shell
$taskShortcut = $taskShell.CreateShortcut((Join-Path $taskPrograms '小狼毫 AI 設定.lnk'))
$taskShortcut.TargetPath = $taskPwsh
$taskShortcut.Arguments = '-STA -NoProfile -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'ai-settings.ps1') + '"'
$taskShortcut.WorkingDirectory = Split-Path $PSScriptRoot -Parent
$taskShortcut.IconLocation = (Join-Path (Split-Path $PSScriptRoot -Parent) 'rime/icons/chinese.ico')
$taskShortcut.Hotkey = 'CTRL+ALT+S'
$taskShortcut.Save()
$taskMonitorShortcut = $taskShell.CreateShortcut((Join-Path $taskPrograms '小狼毫 AI 模型監看.lnk'))
$taskMonitorShortcut.TargetPath = $taskPwsh
$taskMonitorShortcut.Arguments = '-STA -NoProfile -WindowStyle Hidden -File "' + (Join-Path $PSScriptRoot 'ai-monitor.ps1') + '"'
$taskMonitorShortcut.WorkingDirectory = Split-Path $PSScriptRoot -Parent
$taskMonitorShortcut.IconLocation = $taskShortcut.IconLocation
$taskMonitorShortcut.Save()
