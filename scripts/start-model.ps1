#requires -Version 7.0
param(
    [ValidateSet('Laya', 'MlmSlots', 'MlmPll', 'Julia', 'Verdict', 'NanoJev', 'Qwen', 'Jev')][string]$Backend = 'Julia',
    [ValidateSet('semantic', 'rime-sentence', 'rime-aware')][string]$InputMode = 'semantic'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
switch ($Backend) {
    'Jev' { & .venv/Scripts/ime-serve.exe --profile config/reranker-jev.json }
    'Laya' { & .venv/Scripts/ime-serve.exe --backend laya --model models/laya-multilingual }
    'MlmSlots' { & .venv/Scripts/ime-serve.exe --backend mlm --model models/rbt3 }
    'MlmPll' { & .venv/Scripts/ime-serve.exe --backend mlm --mlm-mode pll --model models/rbt3 }
    'Julia' {
        if ($InputMode -eq 'semantic') {
            & .venv/Scripts/ime-serve.exe --profile config/reranker.json
        } else {
            & .venv/Scripts/ime-serve.exe --backend julia --model models/julia --input-mode $InputMode
        }
    }
    'Verdict' { & .venv/Scripts/ime-serve.exe --backend verdict --model models/verdict }
    'NanoJev' { & .venv/Scripts/ime-serve.exe --backend nanojev --model models/nanojev }
    'Qwen' { & .venv/Scripts/ime-serve.exe --backend qwen --model models/qwen3-0.6b --input-mode $InputMode }
}
