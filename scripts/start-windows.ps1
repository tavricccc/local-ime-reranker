#requires -Version 7.0
param([ValidateSet('Julia', 'Jev')][string]$Backend)
. "$PSScriptRoot/windows/common.ps1"
. "$PSScriptRoot/windows/model.ps1"
if (-not $Backend) {
    $Backend = (Get-Content -LiteralPath $AiSettingsPath -Raw | ConvertFrom-Json).backend
}
Assert-OwnFrontend
Set-IsolatedUserData
Start-ModelBackend $Backend ($PSBoundParameters.ContainsKey('Backend'))
$existing = @(Get-Process WeaselServer -ErrorAction SilentlyContinue)
if ($existing.Count) {
    if ($existing[0].Path -ne (Join-Path $Frontend 'WeaselServer.exe')) { throw '另一份小狼毫服務正在執行。' }
    Save-OwnedProcess $existing[0] 'weasel' (Join-Path $Frontend 'WeaselServer.exe')
} else {
    $process = Start-Process -FilePath (Join-Path $Frontend 'WeaselServer.exe') -WorkingDirectory $Frontend -WindowStyle Hidden -PassThru
    Save-OwnedProcess $process 'weasel' (Join-Path $Frontend 'WeaselServer.exe')
}
Write-Host "$Backend 後端已就緒，原生 Rime 已啟動。Ctrl+Alt+A 切換 AI；停止服務仍可正常選字。"
