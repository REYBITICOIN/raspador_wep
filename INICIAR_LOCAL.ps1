$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " WEB INTELLIGENCE LAB - TESTE LOCAL" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$drive = Get-PSDrive -Name C
if ($drive.Free -lt 8GB) {
    throw "Espaco insuficiente no C:. Libere pelo menos 8 GB antes de continuar."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker Desktop nao foi encontrado. Instale/inicie o Docker Desktop e execute este arquivo novamente."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop esta instalado, mas nao esta iniciado."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ""
    Write-Host "As APIs sao opcionais no primeiro teste." -ForegroundColor Yellow
    $nvidia = Read-Host "COLE A CHAVE NVIDIA (ou aperte ENTER para pular)"
    $grokSecure = Read-Host "COLE A CHAVE GROK (ou aperte ENTER para pular)" -AsSecureString
    $grok = [System.Net.NetworkCredential]::new("", $grokSecure).Password

    $envText = Get-Content ".env" -Raw
    if ($nvidia) { $envText = $envText -replace "(?m)^NVIDIA_API_KEY=.*$", "NVIDIA_API_KEY=$nvidia" }
    if ($grok) { $envText = $envText -replace "(?m)^XAI_API_KEY=.*$", "XAI_API_KEY=$grok" }
    Set-Content ".env" $envText -Encoding UTF8
    $nvidia = $null
    $grok = $null
}

New-Item -ItemType Directory -Path "data" -Force | Out-Null
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "Falha ao iniciar os containers." }

Write-Host ""
Write-Host "Aguardando o backend..." -ForegroundColor Cyan
$ready = $false
1..30 | ForEach-Object {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:8080/health" -TimeoutSec 2
        if ($health.status -eq "ok") { $ready = $true }
    } catch {}
    if (-not $ready) { Start-Sleep -Seconds 1 }
}
if (-not $ready) {
    docker compose logs --tail 80
    throw "O backend nao ficou pronto."
}

Write-Host ""
Write-Host "TESTE LOCAL INICIADO COM SUCESSO" -ForegroundColor Green
Write-Host "Painel: http://127.0.0.1:4173" -ForegroundColor Green
Write-Host "API:    http://127.0.0.1:8080/docs" -ForegroundColor Green
Start-Process "http://127.0.0.1:4173"

