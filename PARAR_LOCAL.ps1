$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
docker compose down
Write-Host "Web Intelligence Lab encerrado. Os dados foram preservados na pasta data." -ForegroundColor Green

