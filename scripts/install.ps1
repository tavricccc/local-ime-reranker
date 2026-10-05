#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
. "$PSScriptRoot/windows/common.ps1"
Assert-OwnFrontend
Stop-OwnedProcess 'model'
Stop-OwnedProcess 'weasel'
$env:PYTHONUTF8 = '1'
$env:HF_HUB_DISABLE_PROGRESS_BARS = '1'
Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
Remove-Item Env:TRANSFORMERS_OFFLINE -ErrorAction SilentlyContinue
foreach ($taskDependency in @(@('git','Git.Git'),@('uv','astral-sh.uv'))) {
    if (-not (Get-Command $taskDependency[0] -ErrorAction SilentlyContinue)) {
        & winget install --id $taskDependency[1] --exact --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE) { throw "無法安裝 $($taskDependency[0])" }
        $env:PATH = [Environment]::GetEnvironmentVariable('PATH','Machine') + ';' + [Environment]::GetEnvironmentVariable('PATH','User')
    }
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & uv venv --python 3.12 .venv
    if ($LASTEXITCODE) { throw '建立 Python 環境失敗' }
}
& uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
if ($LASTEXITCODE) { throw '安裝依賴失敗' }
& uv pip install --python .venv/Scripts/python.exe --no-deps -e .
if ($LASTEXITCODE) { throw '安裝模型服務失敗' }
& .venv/Scripts/python.exe scripts/download_assets.py --model julia
if ($LASTEXITCODE) { throw 'Julia 或 librime 下載失敗' }
& (Join-Path $PSScriptRoot 'prepare-windows.ps1')
& (Join-Path $PSScriptRoot 'install-windows.ps1')
& (Join-Path $PSScriptRoot 'install-settings-shortcut.ps1')
& (Join-Path $PSScriptRoot 'enable-startup.ps1')
& (Join-Path $PSScriptRoot 'start-windows.ps1')
Write-Output '安裝完成。首次安裝預設 Julia；登入 Windows 自動啟動，後端選擇會持續保存。Win+Space 選小狼毫。'
