#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$taskSecret = Read-Host '貼上官方 Jev API 金鑰（不會顯示）' -AsSecureString
$taskPlain = [Net.NetworkCredential]::new('', $taskSecret).Password
if ([string]::IsNullOrWhiteSpace($taskPlain)) { throw '未輸入金鑰' }
[Environment]::SetEnvironmentVariable('JEV_API_KEY', $taskPlain, 'User')
$taskPlain = $null
$taskSecret.Dispose()
Write-Host '金鑰已存入目前使用者的 JEV_API_KEY；沒有寫入專案或 Git。'
