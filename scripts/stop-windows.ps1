#requires -Version 7.0
. "$PSScriptRoot/windows/common.ps1"
Stop-OwnedProcess 'model'
Stop-OwnedProcess 'weasel'
Write-Host '已停止這個 PoC 的模型與前端；TSF 註冊和個人詞庫保留。'
