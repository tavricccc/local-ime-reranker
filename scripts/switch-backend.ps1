#requires -Version 7.0
param([Parameter(Mandatory)][ValidateSet('Julia','Jev')][string]$Backend)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$PSStyle.OutputRendering = 'PlainText'
. "$PSScriptRoot/windows/common.ps1"
. "$PSScriptRoot/windows/model.ps1"
Start-ModelBackend $Backend $true
Write-Output "$Backend 已就緒。"
