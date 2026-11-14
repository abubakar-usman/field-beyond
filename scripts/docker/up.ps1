# Build the Docker images, start the app, seed SYNTHETIC demo data and load it into PostGIS.
# Needs only Docker Desktop and git. Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1            # Mars target data (200 m)
#   powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1 -Moon      # also 60 m Moon data (~15 min more)
#   powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1 -NoSeed    # build and start only
#   powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1 -Reseed    # regenerate synthetic data
#   powershell -ExecutionPolicy Bypass -File scripts\docker\up.ps1 -Storage   # also start MinIO
param(
    [switch]$Moon,
    [switch]$NoSeed,
    [switch]$Reseed,
    [switch]$Storage
)
# 'Continue', not 'Stop': in Windows PowerShell 5.1 a redirected native stderr line would
# otherwise abort the script. Every native call's exit code is checked explicitly instead.
$ErrorActionPreference = 'Continue'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root

function Say($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "xx $m" -ForegroundColor Red; exit 1 }
function Invoke-Checked {
    param([string[]]$Cmd)
    & $Cmd[0] $Cmd[1..($Cmd.Length - 1)]
    if ($LASTEXITCODE -ne 0) { Fail "command failed ($LASTEXITCODE): $($Cmd -join ' ')" }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker is not installed (install Docker Desktop)' }
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Fail "the Docker Compose v2 plugin ('docker compose') is required" }
docker info *> $null
if ($LASTEXITCODE -ne 0) { Fail 'the Docker daemon is not running (start Docker Desktop)' }

function New-Secret {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

if (-not (Test-Path '.env')) {
    Say 'creating .env with random local secrets'
    $lines = Get-Content 'infra/.env.example' | ForEach-Object {
        $_ -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret)" `
           -replace '^DEMO_TOKEN=.*', "DEMO_TOKEN=$(New-Secret)" `
           -replace '^MINIO_ROOT_PASSWORD=.*', "MINIO_ROOT_PASSWORD=$(New-Secret)"
    }
    # UTF-8 without BOM so docker compose reads the first key correctly.
    [System.IO.File]::WriteAllLines((Join-Path $Root '.env'), $lines, (New-Object System.Text.UTF8Encoding($false)))
}

$sha = (git rev-parse HEAD 2>$null)
$env:GIT_SHA = if ($LASTEXITCODE -eq 0 -and $sha) { $sha } else { 'unknown' }

$dc = @('docker', 'compose', '--env-file', '.env', '-f', 'infra/docker-compose.yml')
if ($Storage) { $dc += @('--profile', 'storage') }

Say 'building images (first build downloads base images and dependencies)'
Invoke-Checked ($dc + @('build'))

Say 'starting containers'
Invoke-Checked ($dc + @('up', '-d'))

Say 'waiting for the API (migrations run first)'
$probe = "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    & $dc[0] $dc[1..($dc.Length - 1)] exec -T backend python -c $probe *> $null
    if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ok) {
    & $dc[0] $dc[1..($dc.Length - 1)] logs --tail=60 backend
    Fail 'the API did not become healthy; backend logs are above'
}

function Test-Scale($scale) {
    & $dc[0] $dc[1..($dc.Length - 1)] exec -T backend test -f "/data/processed/regions/earth_sahara/current-${scale}m.json" *> $null
    return ($LASTEXITCODE -eq 0)
}

if (-not $NoSeed) {
    if ($Reseed -or -not (Test-Scale 200)) {
        Say 'seeding SYNTHETIC 200 m features (Mars target), about 2-4 min'
        Invoke-Checked ($dc + @('exec', '-T', 'backend', 'pipeline', 'seed-fake', '--scale', '200'))
    } else {
        Say '200 m data already present (use -Reseed to regenerate)'
    }
    if ($Moon -and ($Reseed -or -not (Test-Scale 60))) {
        Say 'seeding SYNTHETIC 60 m features (Moon target), about 15 min'
        Invoke-Checked ($dc + @('exec', '-T', 'backend', 'pipeline', 'seed-fake', '--scale', '60'))
    }
    Say 'loading data into PostGIS'
    Invoke-Checked ($dc + @('exec', '-T', 'backend', 'pipeline', 'load-db'))
}

$envText = Get-Content '.env'
$apiPort = ($envText | Select-String '^API_PORT=(\d+)').Matches.Groups[1].Value
$appPort = ($envText | Select-String '^APP_PORT=(\d+)').Matches.Groups[1].Value
if (-not $apiPort) { $apiPort = '8000' }
if (-not $appPort) { $appPort = '3000' }
Say 'ready'
Write-Host "  App:       http://localhost:$appPort"
Write-Host "  API docs:  http://localhost:$apiPort/docs"
Write-Host "  Health:    http://localhost:$apiPort/health"
Write-Host '  Reviews need the DEMO_TOKEN value from .env'
Write-Host '  Stop:      scripts\docker\down.ps1    Logs: scripts\docker\logs.ps1 [backend|frontend|db]'
