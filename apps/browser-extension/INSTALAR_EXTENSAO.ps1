$extensionPath = "C:\RASPADOR_WEB\apps\browser-extension"
if (-not (Test-Path (Join-Path $extensionPath "manifest.json"))) {
    Write-Host "Extensao nao encontrada em $extensionPath" -ForegroundColor Red
    exit 1
}
Start-Process explorer.exe $extensionPath
Start-Process "chrome://extensions"
Write-Host ""
Write-Host "1. Ative Modo do desenvolvedor." -ForegroundColor Cyan
Write-Host "2. Clique em Carregar sem compactacao." -ForegroundColor Cyan
Write-Host "3. Escolha a pasta aberta no Explorer." -ForegroundColor Cyan
Write-Host "Repita em cada perfil do Chrome." -ForegroundColor Yellow
