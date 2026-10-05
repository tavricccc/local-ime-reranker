#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
Assert-OwnFrontend
if (Get-Process WeaselSetup -ErrorAction SilentlyContinue) { throw '已有小狼毫註冊程序正在等待，請先處理該 UAC 提示。' }
$taskSchema = (Get-Content -LiteralPath (Join-Path $Root 'config/rime-scheme.json') -Raw | ConvertFrom-Json).schema_id
if (-not (Test-Path -LiteralPath (Join-Path $UserData "build/$taskSchema.schema.yaml"))) {
    throw '請先執行 prepare-windows.ps1。'
}
Set-IsolatedUserData
$backup = Join-Path $WindowsRoot 'input-profile-before.json'
if (-not (Test-Path -LiteralPath $backup)) {
    @{ Languages = @(Get-WinUserLanguageList); DefaultOverride = Get-WinDefaultInputMethodOverride } |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $backup -Encoding utf8
}
Write-Host '註冊繁體中文 TSF；Windows 會要求 UAC。保留既有輸入法與預設設定。'
Invoke-NativeTool 'WeaselSetup.exe' '/t'
Assert-OwnFrontend
if (-not (Get-MachineWeaselRoot)) { throw 'TSF 註冊未完成' }
Write-Host '註冊完成。執行 start-windows.ps1，再從 Windows 輸入法清單選擇小狼毫。'
