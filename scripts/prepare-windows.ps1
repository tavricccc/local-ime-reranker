#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
Assert-OwnFrontend
if (Get-Process WeaselSetup -ErrorAction SilentlyContinue) { throw '已有小狼毫註冊程序正在等待，請先完成或取消該 UAC 提示。' }
if (Get-Process WeaselServer -ErrorAction SilentlyContinue) { throw '請先停止小狼毫，再重新準備。' }
if (-not (Get-Command 7z -ErrorAction SilentlyContinue) -and -not (Test-Path 'C:/Program Files/7-Zip/7z.exe')) {
    & winget install --id 7zip.7zip --exact --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE) { throw '7-Zip 安裝失敗' }
}
& $Python scripts/download_windows.py
if ($LASTEXITCODE) { throw 'Windows 資產驗證失敗' }
& $Python scripts/prepare_rime.py
if ($LASTEXITCODE) { throw 'Rime 準備失敗' }
& $Python scripts/prepare_windows.py
if ($LASTEXITCODE) { throw 'Windows 準備失敗' }
Set-IsolatedUserData
Invoke-NativeTool 'WeaselDeployer.exe' '/deploy'
Write-Host '原生檔案與詞典已準備；尚未註冊系統 TSF。'
