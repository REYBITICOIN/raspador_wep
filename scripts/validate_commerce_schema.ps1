$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$file = Join-Path $root "supabase\migrations\20260922_commerce_intelligence.sql"
$sql = Get-Content $file -Raw
$tables = ([regex]::Matches($sql, "create table public\.")).Count
$rls = ([regex]::Matches($sql, "enable row level security")).Count
$policies = ([regex]::Matches($sql, "create policy")).Count
$indexes = ([regex]::Matches($sql, "create index")).Count
if ($tables -ne 8) { throw "Expected 8 tables; got $tables" }
if ($rls -ne 8) { throw "Expected RLS on 8 tables; got $rls" }
if ($policies -ne 8) { throw "Expected 8 ownership policies; got $policies" }
if ($indexes -lt 8) { throw "Expected at least 8 indexes; got $indexes" }
if ($sql -notmatch "\(select auth\.uid\(\)\) = user_id") { throw "Optimized auth.uid ownership check is missing" }
if ($sql -match "security definer") { throw "Unexpected SECURITY DEFINER" }
Write-Output "SCHEMA_OK tables=$tables rls=$rls policies=$policies indexes=$indexes"
