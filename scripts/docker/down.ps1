# Stop the app.
#   powershell -ExecutionPolicy Bypass -File scripts\docker\down.ps1         # keep the database and data
#   powershell -ExecutionPolicy Bypass -File scripts\docker\down.ps1 -Wipe   # also delete the volumes
param([switch]$Wipe)
$ErrorActionPreference = 'Continue'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
if (-not (Test-Path '.env')) { Write-Host 'no .env: nothing was started from this folder'; exit 0 }
$dc = @('compose', '--env-file', '.env', '-f', 'infra/docker-compose.yml', '--profile', 'storage')
if ($Wipe) {
    docker @dc down -v
    Write-Host 'stopped and deleted volumes (database, pipeline data, MinIO)'
} else {
    docker @dc down
    Write-Host 'stopped (data kept; use -Wipe to delete it)'
}
