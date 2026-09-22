$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " WEB INTELLIGENCE LAB - MODO LEVE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$freeGB = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
if ($freeGB -lt 3) { throw "Espaco insuficiente. O modo leve precisa de pelo menos 3 GB livres." }

if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js nao foi encontrado." }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw "npm nao foi encontrado." }

$pythonCommand = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $pythonCommand = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCommand = "python" }
else { throw "Python 3.12 ou superior nao foi encontrado." }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    $envText = Get-Content ".env" -Raw
    $envText = $envText -replace "(?m)^DATA_DIR=.*$", "DATA_DIR=./data"
    $envText = $envText -replace "(?m)^SUPABASE_URL=.*$", "SUPABASE_URL="
    Set-Content ".env" $envText -Encoding UTF8

    Write-Host ""
    Write-Host "As APIs sao opcionais no primeiro teste." -ForegroundColor Yellow
    $nvidiaSecure = Read-Host "COLE A CHAVE NVIDIA (ou aperte ENTER para pular)" -AsSecureString
    $grokSecure = Read-Host "COLE A CHAVE GROK (ou aperte ENTER para pular)" -AsSecureString
    $nvidia = [System.Net.NetworkCredential]::new("", $nvidiaSecure).Password
    $grok = [System.Net.NetworkCredential]::new("", $grokSecure).Password
    $envText = Get-Content ".env" -Raw
    if ($nvidia) { $envText = $envText -replace "(?m)^NVIDIA_API_KEY=.*$", "NVIDIA_API_KEY=$nvidia" }
    if ($grok) { $envText = $envText -replace "(?m)^XAI_API_KEY=.*$", "XAI_API_KEY=$grok" }
    Set-Content ".env" $envText -Encoding UTF8
    $nvidia = $null
    $grok = $null
}

New-Item -ItemType Directory -Path "data" -Force | Out-Null

if (-not (Test-Path ".venv312\Scripts\python.exe")) {
    Write-Host "Criando ambiente Python 3.12..." -ForegroundColor Cyan
    if ($pythonCommand -eq "py") { & py -3.12 -m venv .venv312 } else { & python -m venv .venv312 }
}

Write-Host "Instalando dependencias leves do backend..." -ForegroundColor Cyan
& ".\.venv312\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r "services\api\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar dependencias Python." }

Write-Host "Instalando dependencias do painel..." -ForegroundColor Cyan
Push-Location "apps\dashboard"
& npm.cmd install --ignore-scripts --no-audit --no-fund
$npmExit = $LASTEXITCODE
Pop-Location
if ($npmExit -ne 0) { throw "Falha ao instalar dependencias do painel." }

$backend = Start-Process -FilePath "$Project\.venv312\Scripts\python.exe" -ArgumentList "-m","uvicorn","services.api.app.main:app","--host","127.0.0.1","--port","8080" -WorkingDirectory $Project -PassThru
$frontend = Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm.cmd run dev -- --host 127.0.0.1 --port 4173" -WorkingDirectory "$Project\apps\dashboard" -PassThru
@{ backend = $backend.Id; frontend = $frontend.Id } | ConvertTo-Json | Set-Content ".local-processes.json" -Encoding UTF8

Write-Host "Aguardando o sistema..." -ForegroundColor Cyan
$ready = $false
1..30 | ForEach-Object {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:8080/health" -TimeoutSec 2
        if ($health.status -eq "ok") { $ready = $true }
    } catch {}
    if (-not $ready) { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw "O backend nao ficou pronto. Execute PARAR_SEM_DOCKER.ps1 e tente novamente." }

Write-Host ""
Write-Host "PAINEL PRONTO: http://127.0.0.1:4173" -ForegroundColor Green
Write-Host "API:          http://127.0.0.1:8080/docs" -ForegroundColor Green
Start-Process "http://127.0.0.1:4173"

