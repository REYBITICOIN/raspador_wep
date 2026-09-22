$ErrorActionPreference = "Stop"
$Root = "C:\RASPADOR_WEB"

Write-Host "Instalando o núcleo Crawl4AI..." -ForegroundColor Cyan
Set-Location $Root

& "$Root\.venv312\Scripts\python.exe" -m pip install "crawl4ai==0.8.7"
& "$Root\.venv312\Scripts\python.exe" -m playwright install chromium

Write-Host "Validando a instalação..." -ForegroundColor Cyan
& "$Root\.venv312\Scripts\python.exe" -c "from crawl4ai import AsyncWebCrawler; print('CRAWL4AI_OK')"

Write-Host "Instalação concluída." -ForegroundColor Green
