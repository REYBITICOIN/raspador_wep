$ErrorActionPreference = "Stop"
$Target = "C:\RASPADOR_WEB"

Write-Host ""
Write-Host "Instalando em $Target" -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git nao foi encontrado no computador."
}
if (Test-Path $Target) {
    Set-Location $Target
    git pull --ff-only
} else {
    git clone https://github.com/REYBITICOIN/raspador_wep.git $Target
    Set-Location $Target
}
& "$Target\INICIAR_LOCAL.ps1"
