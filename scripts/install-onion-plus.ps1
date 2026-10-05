#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
Stop-OwnedProcess 'weasel'
& $Python (Join-Path $PSScriptRoot 'stage_onion_plus.py')
if ($LASTEXITCODE) { throw '洋蔥 Plus 檔案安裝失敗' }
Invoke-NativeTool 'WeaselDeployer.exe' '/deploy'
& (Join-Path $PSScriptRoot 'start-windows.ps1')
