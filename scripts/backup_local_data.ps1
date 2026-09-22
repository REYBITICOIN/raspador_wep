$ErrorActionPreference = "Stop"

$root = "G:\TOCA_COMMERCE_DATA"
$backupRoot = Join-Path $root "backups"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force -Path $target | Out-Null

$python = "C:\RASPADOR_WEB\.venv312\Scripts\python.exe"
$sourceDb = Join-Path $root "database\commerce.db"
$backupDb = Join-Path $target "commerce.db"

if (Test-Path $sourceDb) {
  & $python -c "import sqlite3; s=sqlite3.connect(r'$sourceDb'); d=sqlite3.connect(r'$backupDb'); s.backup(d); d.close(); s.close()"
  if ($LASTEXITCODE -ne 0) { throw "SQLite backup failed" }
}

$paths = @(
  @{ Source = (Join-Path $root "app-data"); Name = "app-data.zip" },
  @{ Source = (Join-Path $root "obsidian"); Name = "obsidian.zip" }
)
foreach ($item in $paths) {
  if (Test-Path $item.Source) {
    Compress-Archive -Path (Join-Path $item.Source "*") -DestinationPath (Join-Path $target $item.Name) -Force
  }
}

$manifest = Get-ChildItem $target -File | ForEach-Object {
  [pscustomobject]@{
    file = $_.Name
    bytes = $_.Length
    sha256 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
  }
}
$manifest | ConvertTo-Json | Set-Content (Join-Path $target "manifest.json") -Encoding UTF8

Write-Output "BACKUP_OK $target"

