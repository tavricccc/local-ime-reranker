#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
Assert-OwnFrontend
if (Get-Process WeaselSetup -ErrorAction SilentlyContinue) { throw '已有小狼毫註冊程序正在等待，請先完成或取消該 UAC 提示。' }
if (Get-MachineWeaselRoot) {
    Invoke-NativeTool 'WeaselSetup.exe' '/u'
    if (Get-MachineWeaselRoot) { throw '小狼毫 TSF 仍已註冊，未還原偏好。' }
}
Stop-OwnedProcess 'model'
Stop-OwnedProcess 'weasel'
$backup = Join-Path $WindowsRoot 'registry-backup.json'
if (Test-Path -LiteralPath $backup) {
    $saved = Get-Content -LiteralPath $backup -Raw | ConvertFrom-Json -AsHashtable
    $current = Get-ItemPropertyValue -LiteralPath $RegistryPath -Name RimeUserDir -ErrorAction SilentlyContinue
    if ($current -and [IO.Path]::GetFullPath($current) -ne [IO.Path]::GetFullPath($UserData)) { throw 'Rime 資料路徑已被另外修改，不還原偏好。' }
    if (Test-Path -LiteralPath $RegistryPath) { Remove-Item -LiteralPath $RegistryPath -Recurse }
    if ($saved.Existed) {
        New-Item -Path $RegistryPath -Force | Out-Null
        foreach ($name in $saved.Values.Keys) { Set-ItemProperty -LiteralPath $RegistryPath -Name $name -Value $saved.Values[$name] }
    }
}
Write-Host 'TSF 已移除並還原原先 Rime 偏好；實驗詞庫與模型檔案保留於 runtime／models。'
