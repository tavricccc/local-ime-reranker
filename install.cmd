@echo off
where pwsh >nul 2>&1
if errorlevel 1 (
  winget install --id Microsoft.PowerShell --exact --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 exit /b 1
  "%ProgramFiles%\PowerShell\7\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
) else (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
)
pause
