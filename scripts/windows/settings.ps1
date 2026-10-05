$script:AiSettingsDir = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'LocalImeReranker'
$script:AiSettingsPath = Join-Path $AiSettingsDir 'settings.json'
$script:AiPromptPath = Join-Path $AiSettingsDir 'ai-prompt.txt'
function Initialize-AiSettings([string]$ProjectRoot) {
    New-Item -Path $AiSettingsDir -ItemType Directory -Force | Out-Null
    if (-not (Test-Path -LiteralPath $AiSettingsPath)) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot 'config/ai-settings.json') -Destination $AiSettingsPath
    }
    if (-not (Test-Path -LiteralPath $AiPromptPath)) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot 'config/ai-prompt.txt') -Destination $AiPromptPath
    }
}
