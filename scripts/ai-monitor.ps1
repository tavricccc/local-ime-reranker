#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPwsh = (Get-Process -Id $PID).Path
$taskCreated = $false
$taskMutex = [Threading.Mutex]::new($true, 'Local\LocalImeAiMonitor', [ref]$taskCreated)
if (-not $taskCreated) { $taskMutex.Dispose(); return }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::SetHighDpiMode([Windows.Forms.HighDpiMode]::PerMonitorV2) | Out-Null
[Windows.Forms.Application]::EnableVisualStyles()
$taskForm = [Windows.Forms.Form]::new()
$taskForm.Text = '小狼毫 AI 模型監看'
$taskForm.Font = [Drawing.Font]::new('Microsoft JhengHei UI', 10)
$taskForm.AutoScaleMode = 'Dpi'
$taskForm.ClientSize = [Drawing.Size]::new(960, 520)
$taskForm.MinimumSize = [Drawing.Size]::new(760, 420)
$taskForm.StartPosition = 'CenterScreen'
$taskForm.ShowIcon = $false
$taskLayout = [Windows.Forms.TableLayoutPanel]::new()
$taskLayout.Dock = 'Fill'
$taskLayout.Padding = [Windows.Forms.Padding]::new(16)
$taskLayout.ColumnCount = 1
$taskLayout.RowCount = 5
foreach ($taskHeight in @(32,52,28)) { $taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Absolute',$taskHeight)) | Out-Null }
$taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Percent',100)) | Out-Null
$taskLayout.RowStyles.Add([Windows.Forms.RowStyle]::new('Absolute',42)) | Out-Null
$taskForm.Controls.Add($taskLayout)
function Add-MonitorLabel([string]$Text,[int]$Row) {
    $taskLabel = [Windows.Forms.Label]::new()
    $taskLabel.Text = $Text
    $taskLabel.Dock = 'Fill'
    $taskLabel.TextAlign = 'MiddleLeft'
    $taskLayout.Controls.Add($taskLabel,0,$Row)
    return $taskLabel
}
$taskState = Add-MonitorLabel '正在連線至模型服務…' 0
$taskStats = Add-MonitorLabel '尚無推論資料。正常輸入並提交一小段中文後，才會開始依上下文判斷。' 1
Add-MonitorLabel '模型耗時與輸入法等待分開計算；快取不列入模型推論 P50／P95。' 2 | Out-Null
$taskGrid = [Windows.Forms.DataGridView]::new()
$taskGrid.Dock = 'Fill'
$taskGrid.ReadOnly = $true
$taskGrid.AllowUserToAddRows = $false
$taskGrid.AllowUserToDeleteRows = $false
$taskGrid.RowHeadersVisible = $false
$taskGrid.SelectionMode = 'FullRowSelect'
$taskGrid.MultiSelect = $false
$taskGrid.AutoSizeColumnsMode = 'Fill'
$taskGrid.BackgroundColor = [Drawing.SystemColors]::Window
$taskGrid.BorderStyle = 'FixedSingle'
foreach ($taskColumn in @(@('time','時間'),@('kind','事件'),@('inference','模型 ms'),@('total','等待／處理 ms'),@('count','候選數'),@('winner','選中順位'),@('scope','完整／片段'),@('reason','結果'))) {
    [void]$taskGrid.Columns.Add($taskColumn[0],$taskColumn[1])
}
$taskGrid.Columns['reason'].FillWeight = 190
$taskLayout.Controls.Add($taskGrid,0,3)
$taskButtons = [Windows.Forms.FlowLayoutPanel]::new()
$taskButtons.Dock = 'Fill'
$taskLayout.Controls.Add($taskButtons,0,4)
$taskPause = [Windows.Forms.CheckBox]::new()
$taskPause.Text = '暫停更新'
$taskPause.AutoSize = $true
$taskPause.Margin = [Windows.Forms.Padding]::new(3,10,16,3)
$taskButtons.Controls.Add($taskPause)
function Add-MonitorButton([string]$Text,[scriptblock]$Action) {
    $taskButton = [Windows.Forms.Button]::new()
    $taskButton.Text = $Text
    $taskButton.AutoSize = $true
    $taskButton.Height = 32
    $taskButton.Add_Click($Action)
    $taskButtons.Controls.Add($taskButton)
}
Add-MonitorButton 'AI 設定' { Start-Process -FilePath $taskPwsh -WindowStyle Hidden -ArgumentList "-STA -NoProfile -File `"$PSScriptRoot/ai-settings.ps1`"" }
Add-MonitorButton '服務錯誤 log' { Start-Process notepad.exe -ArgumentList ('"'+$taskRoot+'/runtime/windows/model.stderr.log"') }
Add-MonitorButton '另存紀錄' {
    if (-not $script:taskSnapshot) { return }
    $taskDialog = [Windows.Forms.SaveFileDialog]::new()
    $taskDialog.Filter = 'JSON 紀錄 (*.json)|*.json'
    $taskDialog.FileName = 'ai-monitor.json'
    if ($taskDialog.ShowDialog($taskForm) -eq 'OK') {
        $script:taskSnapshot | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $taskDialog.FileName -Encoding utf8
    }
    $taskDialog.Dispose()
}
function Format-Milliseconds($Value) {
    if ($null -eq $Value) { return '—' }
    return ([double]$Value).ToString('0.0')
}
function Update-Monitor {
    if ($taskPause.Checked) { return }
    $taskClient = [Net.Sockets.TcpClient]::new()
    try {
        if (-not $taskClient.ConnectAsync('127.0.0.1',18963).Wait(60)) { throw 'Offline' }
        $taskStream = $taskClient.GetStream()
        $taskStream.ReadTimeout = 150
        $taskStream.WriteTimeout = 150
        $taskWriter = [IO.StreamWriter]::new($taskStream,[Text.UTF8Encoding]::new($false),1024,$true)
        $taskWriter.WriteLine('{"diagnostic":"status"}')
        $taskWriter.Flush()
        $taskReader = [IO.StreamReader]::new($taskStream,[Text.Encoding]::UTF8,$false,1024,$true)
        $script:taskSnapshot = $taskReader.ReadLine() | ConvertFrom-Json
        $taskWriter.Dispose()
        $taskReader.Dispose()
        $taskData = $script:taskSnapshot
        $taskMode = if ($taskData.backend -eq 'jev') { '官方 API' } else { '本地 CPU' }
        $taskActivity = if ($taskData.state -eq 'inference') { '正在判斷' } else { '已就緒，等待輸入' }
        $taskState.Text = "$($taskData.backend) · $taskMode · $taskActivity · PID $($taskData.pid)"
        $taskState.ForeColor = [Drawing.SystemColors]::ControlText
        $taskStats.Text = "模型 P50 / P95：$(Format-Milliseconds $taskData.inference_p50_ms) / $(Format-Milliseconds $taskData.inference_p95_ms) ms    輸入法 P50 / P95：$(Format-Milliseconds $taskData.ime_p50_ms) / $(Format-Milliseconds $taskData.ime_p95_ms) ms`n判斷 $([int]$taskData.counts.decision)    快取 $([int]$taskData.counts.cache)    忙碌 $([int]$taskData.counts.busy)    錯誤 $([int]$taskData.counts.error)"
        if ($taskData.events.Count -and $script:taskLastEvent -ne $taskData.events[-1].id) {
            $script:taskLastEvent = $taskData.events[-1].id
            $taskGrid.Rows.Clear()
            foreach ($taskEvent in @($taskData.events | Sort-Object id -Descending)) {
                $taskKind = @{ready='就緒';decision='模型判斷';cache='快取';busy='忙碌';error='錯誤';ime='輸入法'}[$taskEvent.kind]
                $taskReason = ''
                if ($taskEvent.reason) { $taskReason = @{accepted='採用排序';low_confidence='保留原排序';model_abstained='模型棄權';returned='已回傳';timeout_or_disconnect='逾時／斷線'}[$taskEvent.reason] }
                if ($taskEvent.kind -eq 'error') { $taskReason = $taskEvent.error }
                $taskElapsed = if ($taskEvent.kind -eq 'ime') { $taskEvent.elapsed_ms } else { $taskEvent.total_ms }
                $taskScope = if ($null -ne $taskEvent.partial) { if ($taskEvent.partial) { '片段' } else { '完整' } } else { '' }
                [void]$taskGrid.Rows.Add(([datetime]$taskEvent.time).ToLocalTime().ToString('HH:mm:ss.fff'), $taskKind, (Format-Milliseconds $taskEvent.inference_ms), (Format-Milliseconds $taskElapsed), $taskEvent.candidates, $taskEvent.winner, $taskScope, $taskReason)
            }
        }
    } catch {
        $taskState.ForeColor = [Drawing.Color]::Firebrick
        $taskState.Text = '模型服務未連線。'
        $taskStatusPath = Join-Path $taskRoot 'runtime/windows/model-status.json'
        if (Test-Path -LiteralPath $taskStatusPath) {
            $taskSaved = Get-Content -LiteralPath $taskStatusPath -Raw | ConvertFrom-Json
            if (Get-Process -Id $taskSaved.pid -ErrorAction SilentlyContinue) {
                $taskState.Text = "$($taskSaved.backend) · 載入中或服務尚未就緒。"
            }
        }
        $taskStats.Text = '此視窗每秒讀取狀態，不會主動要求模型推論。紀錄不含輸入內容與金鑰。'
    } finally { $taskClient.Dispose() }
}
$taskTimer = [Windows.Forms.Timer]::new()
$taskTimer.Interval = 1000
$taskTimer.Add_Tick({ Update-Monitor })
$taskForm.Add_Shown({ Update-Monitor; $taskTimer.Start() })
try { $taskForm.ShowDialog() | Out-Null } finally {
    $taskTimer.Dispose()
    $taskForm.Dispose()
    $taskMutex.ReleaseMutex()
    $taskMutex.Dispose()
}
