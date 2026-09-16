$ErrorActionPreference = "SilentlyContinue"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (Test-Path ".local-processes.json") {
    $processes = Get-Content ".local-processes.json" -Raw | ConvertFrom-Json
    Stop-Process -Id $processes.backend -Force
    Stop-Process -Id $processes.frontend -Force
    Remove-Item ".local-processes.json" -Force
}
Write-Host "Web Intelligence Lab encerrado. Os dados foram preservados." -ForegroundColor Green
