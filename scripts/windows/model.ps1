function Start-ModelBackend([string]$Backend, [bool]$Restart) {
    if ($Restart) { Stop-OwnedProcess 'model' }
    $taskProfile = if ($Backend -eq 'Jev') { 'config/reranker-jev.json' } else { 'config/reranker.json' }
    if (-not (Get-OwnedProcess 'model')) {
        $taskModelProcess = Start-Process -FilePath $Python -ArgumentList "-m ime_reranker.server --profile $taskProfile" -WorkingDirectory $Root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $WindowsRoot 'model.stdout.log') -RedirectStandardError (Join-Path $WindowsRoot 'model.stderr.log')
        Save-OwnedProcess $taskModelProcess 'model' $Python
    }
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(30)
    while ([DateTime]::UtcNow -lt $taskDeadline) {
        $taskSignal = $null
        if ([Threading.EventWaitHandle]::TryOpenExisting('Local\LocalImeRerankerReady', [ref]$taskSignal)) {
            $taskReady = $taskSignal.WaitOne(0)
            $taskSignal.Dispose()
            if ($taskReady) { return }
        }
        if (-not (Get-OwnedProcess 'model')) { throw '模型啟動失敗，請查看 runtime/windows/model.stderr.log。' }
        Start-Sleep -Milliseconds 200
    }
    throw '模型在 30 秒內尚未就緒，請查看 runtime/windows/model.stderr.log。'
}
