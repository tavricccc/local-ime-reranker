#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$script:Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$script:WindowsRoot = Join-Path $Root 'runtime/windows'
$script:Frontend = Join-Path $WindowsRoot 'weasel'
$script:UserData = Join-Path $WindowsRoot 'user'
$script:Python = Join-Path $Root '.venv/Scripts/python.exe'
$script:RegistryPath = 'HKCU:/Software/Rime/Weasel'
. "$PSScriptRoot/settings.ps1"
Initialize-AiSettings $Root
Set-Location $Root
$env:PYTHONUTF8 = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'

function Get-MachineWeaselRoot {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey('LocalMachine', 'Registry32')
    $key = $base.OpenSubKey('Software\Rime\Weasel')
    try { if ($key) { $key.GetValue('WeaselRoot') } } finally {
        if ($key) { $key.Dispose() }
        $base.Dispose()
    }
}

function Assert-OwnFrontend {
    $installed = Get-MachineWeaselRoot
    if ($installed -and [IO.Path]::GetFullPath($installed) -ne [IO.Path]::GetFullPath($Frontend)) {
        throw "已有另一份小狼毫：$installed；不覆寫其註冊或個人詞庫。"
    }
}

function Invoke-NativeTool([string]$Name, [string]$Argument) {
    $process = Start-Process -FilePath (Join-Path $Frontend $Name) -ArgumentList $Argument -WorkingDirectory $Frontend -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) {
        throw "$Name 尚未完成；請處理 Windows UAC 提示後再執行 Status。"
    }
    if ($process.ExitCode) { throw "$Name 結束碼 $($process.ExitCode)" }
}

function Save-OwnedProcess($Process, [string]$Name, [string]$Executable) {
    @{ Id = $Process.Id; StartTicks = $Process.StartTime.ToUniversalTime().Ticks; Path = $Executable } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $WindowsRoot "$Name.process.json") -Encoding utf8
}

function Get-OwnedProcess([string]$Name) {
    $record = Join-Path $WindowsRoot "$Name.process.json"
    if (Test-Path -LiteralPath $record) {
        $saved = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
        $process = Get-Process -Id $saved.Id -ErrorAction SilentlyContinue
        if ($process -and $process.Path -eq $saved.Path -and $process.StartTime.ToUniversalTime().Ticks -eq $saved.StartTicks) { $process }
    }
}

function Stop-OwnedProcess([string]$Name) {
    $process = Get-OwnedProcess $Name
    if ($process) { & taskkill.exe /PID $process.Id /T /F | Out-Null }
    $record = Join-Path $WindowsRoot "$Name.process.json"
    if (Test-Path -LiteralPath $record) { Remove-Item -LiteralPath $record }
}

function Set-IsolatedUserData {
    $backup = Join-Path $WindowsRoot 'registry-backup.json'
    if (-not (Test-Path -LiteralPath $backup)) {
        $values = @{}
        $existed = Test-Path -LiteralPath $RegistryPath
        if ($existed) {
            $key = Get-Item -LiteralPath $RegistryPath
            foreach ($name in $key.GetValueNames()) { $values[$name] = $key.GetValue($name) }
        }
        @{ Existed = $existed; Values = $values } | ConvertTo-Json -Depth 4 |
            Set-Content -LiteralPath $backup -Encoding utf8
    }
    $current = (Get-ItemProperty -LiteralPath $RegistryPath -ErrorAction SilentlyContinue).RimeUserDir
    if ($current -and [IO.Path]::GetFullPath($current) -ne [IO.Path]::GetFullPath($UserData)) {
        throw "已有 Rime 個人資料路徑：$current；不接管該資料夾。"
    }
    New-Item -Path $RegistryPath -Force | Out-Null
    New-ItemProperty -LiteralPath $RegistryPath -Name RimeUserDir -Value $UserData -PropertyType String -Force | Out-Null
    New-ItemProperty -LiteralPath $RegistryPath -Name Language -Value 'cht' -PropertyType String -Force | Out-Null
}
