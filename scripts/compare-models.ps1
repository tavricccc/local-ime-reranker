#requires -Version 7.0
param([string]$Cases = 'data/comparison_snapshots.json')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Run sequentially: concurrent CPU inference would distort latency measurements.
$jobs = @(
    @{Name='laya-cpu'; Args=@('--backend','laya','--model','models/laya-multilingual')},
    @{Name='rbt3-slots-cpu'; Args=@('--backend','mlm','--model','models/rbt3')},
    @{Name='rbt3-pll-cpu'; Args=@('--backend','mlm','--mlm-mode','pll','--model','models/rbt3')},
    @{Name='julia-cpu'; Args=@('--backend','julia','--model','models/julia')},
    @{Name='verdict-cpu'; Args=@('--backend','verdict','--model','models/verdict')},
    @{Name='nanojev-cpu'; Args=@('--backend','nanojev','--model','models/nanojev')},
    @{Name='qwen-cpu'; Args=@('--backend','qwen','--model','models/qwen3-0.6b')},
    @{Name='julia-rime-sentence-cpu'; Args=@('--backend','julia','--model','models/julia','--input-mode','rime-sentence')},
    @{Name='julia-rime-aware-cpu'; Args=@('--backend','julia','--model','models/julia','--input-mode','rime-aware')},
    @{Name='qwen-rime-aware-cpu'; Args=@('--backend','qwen','--model','models/qwen3-0.6b','--input-mode','rime-aware')}
)
foreach ($job in $jobs) {
    $arguments = $job.Args + @('--cases', $Cases, '--output', ('results/'+$job.Name))
    & .venv/Scripts/ime-evaluate.exe @arguments
    if ($LASTEXITCODE) { throw ('評估失敗：'+$job.Name) }
}
