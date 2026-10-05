#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
. "$PSScriptRoot/windows/settings.ps1"
Initialize-AiSettings $taskRoot
$taskSettingsPath = $AiSettingsPath
$taskPromptPath = $AiPromptPath
$taskPwsh = (Get-Process -Id $PID).Path
$taskNewInstance = $false
$taskMutex = [Threading.Mutex]::new($true, 'Local\LocalImeAiSettings', [ref]$taskNewInstance)
if (-not $taskNewInstance) { $taskMutex.Dispose(); return }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::SetHighDpiMode([Windows.Forms.HighDpiMode]::PerMonitorV2) | Out-Null
[Windows.Forms.Application]::EnableVisualStyles()
$taskForm = [Windows.Forms.Form]::new()
$taskForm.Text = '小狼毫 AI 設定'
$taskForm.Font = [Drawing.Font]::new('Microsoft JhengHei UI', 10)
$taskForm.AutoScaleMode = 'Dpi'
$taskForm.ClientSize = [Drawing.Size]::new(620, 540)
$taskForm.MinimumSize = [Drawing.Size]::new(540, 480)
$taskForm.StartPosition = 'CenterScreen'
$taskForm.ShowIcon = $false
$taskLayout = [Windows.Forms.TableLayoutPanel]::new()
$taskLayout.Dock = 'Fill'
$taskLayout.Padding = [Windows.Forms.Padding]::new(20)
$taskLayout.ColumnCount = 1
$taskLayout.RowCount = 9
foreach ($taskHeight in @(26,32,34,26,34,30)) {
    $taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Absolute', $taskHeight)) | Out-Null
}
$taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Percent', 100)) | Out-Null
$taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Absolute', 46)) | Out-Null
$taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Absolute', 38)) | Out-Null
$taskForm.Controls.Add($taskLayout)
function Add-SettingsLabel([string]$Text, [int]$Row) {
    $taskLabel = [Windows.Forms.Label]::new()
    $taskLabel.Text = $Text
    $taskLabel.Dock = 'Fill'
    $taskLabel.TextAlign = 'MiddleLeft'
    $taskLayout.Controls.Add($taskLabel, 0, $Row)
    return $taskLabel
}
Add-SettingsLabel 'AI 後端' 0 | Out-Null
$taskBackend = [Windows.Forms.ComboBox]::new()
$taskBackend.DropDownStyle = 'DropDownList'
$taskBackend.Dock = 'Fill'
$taskBackend.Items.AddRange(@('Jev（官方 API）', 'Julia（本地）'))
$taskConfig = Get-Content -LiteralPath $taskSettingsPath -Raw | ConvertFrom-Json
$taskBackend.SelectedIndex = if ($taskConfig.backend -eq 'Julia') { 1 } else { 0 }
$taskLayout.Controls.Add($taskBackend, 0, 1)
$taskDescription = Add-SettingsLabel '' 2
Add-SettingsLabel 'Jev API 金鑰' 3 | Out-Null
$taskKeyRow = [Windows.Forms.TableLayoutPanel]::new()
$taskKeyRow.Dock = 'Fill'
$taskKeyRow.ColumnCount = 2
$taskKeyRow.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new('Percent',100)) | Out-Null
$taskKeyRow.ColumnStyles.Add([Windows.Forms.ColumnStyle]::new('Absolute',80)) | Out-Null
$taskKey = [Windows.Forms.TextBox]::new()
$taskKey.Dock = 'Fill'
$taskKey.UseSystemPasswordChar = $true
$taskKey.Text = [Environment]::GetEnvironmentVariable('JEV_API_KEY','User')
if (-not $taskKey.Text) { $taskKey.Text = [Environment]::GetEnvironmentVariable('TYPESAFE_API_KEY','User') }
$taskReveal = [Windows.Forms.CheckBox]::new()
$taskReveal.Text = '顯示'
$taskReveal.Dock = 'Fill'
$taskReveal.Add_CheckedChanged({ $taskKey.UseSystemPasswordChar = -not $taskReveal.Checked })
$taskKeyRow.Controls.Add($taskKey,0,0)
$taskKeyRow.Controls.Add($taskReveal,1,0)
$taskLayout.Controls.Add($taskKeyRow,0,4)
Add-SettingsLabel '提示詞（Jev 與 Julia 共用）' 5 | Out-Null
$taskPrompt = [Windows.Forms.TextBox]::new()
$taskPrompt.Multiline = $true
$taskPrompt.AcceptsReturn = $true
$taskPrompt.ScrollBars = 'Vertical'
$taskPrompt.Dock = 'Fill'
$taskPrompt.Text = [IO.File]::ReadAllText($taskPromptPath)
$taskLayout.Controls.Add($taskPrompt,0,6)
$taskStatus = Add-SettingsLabel 'Ctrl＋Alt＋A 切換 AI；Ctrl＋Alt＋S 開啟此設定。' 7
$taskButtons = [Windows.Forms.FlowLayoutPanel]::new()
$taskButtons.Dock = 'Fill'
$taskButtons.FlowDirection = 'RightToLeft'
$taskCancel = [Windows.Forms.Button]::new()
$taskCancel.Text = '關閉'
$taskCancel.Size = [Drawing.Size]::new(88,30)
$taskCancel.Add_Click({ $taskForm.Close() })
$taskSave = [Windows.Forms.Button]::new()
$taskSave.Text = '儲存並套用'
$taskSave.Size = [Drawing.Size]::new(120,30)
$taskButtons.Controls.Add($taskCancel)
$taskButtons.Controls.Add($taskSave)
$taskMonitor = [Windows.Forms.Button]::new()
$taskMonitor.Text = '模型監看'
$taskMonitor.Size = [Drawing.Size]::new(100,30)
$taskMonitor.Add_Click({ Start-Process -FilePath $taskPwsh -WindowStyle Hidden -ArgumentList "-STA -NoProfile -File `"$PSScriptRoot/ai-monitor.ps1`"" })
$taskButtons.Controls.Add($taskMonitor)
$taskLayout.Controls.Add($taskButtons,0,8)
$taskForm.CancelButton = $taskCancel
function Update-BackendDescription {
    $taskDescription.Text = if ($taskBackend.SelectedIndex -eq 0) { 'Jev 會將上下文、注音與候選送至官方 API。' } else { 'Julia 在本機執行，不需 API 金鑰。' }
}
$taskBackend.Add_SelectedIndexChanged({ Update-BackendDescription })
Update-BackendDescription
$taskTimer = [Windows.Forms.Timer]::new()
$taskTimer.Interval = 300
$taskTimer.Add_Tick({
    if ($script:taskApplyProcess.HasExited) {
        $taskTimer.Stop()
        $taskSave.Enabled = $true
        if ($script:taskApplyProcess.ExitCode -eq 0) {
            $taskStatus.ForeColor = [Drawing.SystemColors]::ControlText
            $taskStatus.Text = '已套用。提示詞後續變更會在下一次判斷生效。'
        } else {
            $taskStatus.ForeColor = [Drawing.Color]::Firebrick
            $taskStatus.Text = '設定已儲存，後端啟動失敗。請檢查 runtime/windows/settings-apply-error.log。'
        }
        $script:taskApplyProcess.Dispose()
    }
})
$taskSave.Add_Click({
    if ($taskBackend.SelectedIndex -eq 0 -and [string]::IsNullOrWhiteSpace($taskKey.Text)) {
        $taskStatus.ForeColor = [Drawing.Color]::Firebrick
        $taskStatus.Text = '請輸入官方 Jev API 金鑰，或選擇本地 Julia。'
        $taskKey.Focus() | Out-Null
        return
    }
    if ([string]::IsNullOrWhiteSpace($taskPrompt.Text)) {
        $taskStatus.ForeColor = [Drawing.Color]::Firebrick
        $taskStatus.Text = '請填寫提示詞。'
        $taskPrompt.Focus() | Out-Null
        return
    }
    try {
        $taskSelected = if ($taskBackend.SelectedIndex -eq 0) { 'Jev' } else { 'Julia' }
        [Environment]::SetEnvironmentVariable('JEV_API_KEY', $taskKey.Text.Trim(), 'User')
        [Environment]::SetEnvironmentVariable('TYPESAFE_API_KEY', $null, 'User')
        $env:JEV_API_KEY = $taskKey.Text.Trim()
        $env:TYPESAFE_API_KEY = $null
        @{backend=$taskSelected} | ConvertTo-Json | Set-Content -LiteralPath $taskSettingsPath -Encoding utf8
        [IO.File]::WriteAllText($taskPromptPath, $taskPrompt.Text.Trim(), [Text.UTF8Encoding]::new($false))
        $taskSave.Enabled = $false
        $taskStatus.ForeColor = [Drawing.SystemColors]::ControlText
        $taskStatus.Text = '正在套用後端；Rime 仍可正常選字。'
        $script:taskApplyProcess = Start-Process -FilePath $taskPwsh -WindowStyle Hidden -ArgumentList "-NoProfile -File `"$PSScriptRoot/switch-backend.ps1`" -Backend $taskSelected" -WorkingDirectory $taskRoot -PassThru -RedirectStandardOutput "$taskRoot/runtime/windows/settings-apply.log" -RedirectStandardError "$taskRoot/runtime/windows/settings-apply-error.log"
        $taskTimer.Start()
    } catch {
        $taskSave.Enabled = $true
        $taskStatus.ForeColor = [Drawing.Color]::Firebrick
        $taskStatus.Text = '無法儲存設定或啟動後端。'
    }
})
try { $taskForm.ShowDialog() | Out-Null } finally {
    $taskTimer.Dispose()
    $taskKey.Text = ''
    $taskForm.Dispose()
    $taskMutex.ReleaseMutex()
    $taskMutex.Dispose()
}
