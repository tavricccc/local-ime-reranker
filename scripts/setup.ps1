#requires -Version 7.0
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:HF_HUB_DISABLE_PROGRESS_BARS = '1'
Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
uv venv --python 3.12 .venv
if ($LASTEXITCODE) { throw '建立 Python 環境失敗' }
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt
if ($LASTEXITCODE) { throw '安裝依賴失敗' }
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
if ($LASTEXITCODE) { throw '安裝 PoC 失敗' }
& .venv/Scripts/python.exe scripts/download_assets.py
if ($LASTEXITCODE) { throw '下載模型或 librime 失敗' }
& .venv/Scripts/python.exe scripts/prepare_rime.py
if ($LASTEXITCODE) { throw '準備 Rime 或編譯 bridge 失敗' }
Write-Host '完成。這是隔離的 headless PoC，不會註冊或切換系統輸入法。'
