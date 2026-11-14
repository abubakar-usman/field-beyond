# Start the app locally.
#   powershell -File scripts/local/dev.ps1            # Docker: PostGIS + MinIO + API + frontend
#   powershell -File scripts/local/dev.ps1 -NoDocker  # no Docker: in-memory store, API + frontend dev servers
# Both modes seed SYNTHETIC features first if none exist (pipeline seed-fake).
param(
    [switch]$NoDocker,
    [switch]$Reseed
)
$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $wg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($wg) { return $wg.FullName }
    throw 'uv not found: winget install astral-sh.uv'
}
$uv = Find-Uv

function New-Secret { -join ((1..24) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) }

if (-not (Test-Path '.env')) {
    Write-Host '==> writing .env with random local secrets'
    (Get-Content 'infra/.env.example') `
        -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret)" `
        -replace '^DEMO_TOKEN=.*', "DEMO_TOKEN=$(New-Secret)" `
        -replace '^MINIO_ROOT_PASSWORD=.*', "MINIO_ROOT_PASSWORD=$(New-Secret)" |
        Set-Content -Encoding utf8 '.env'
}

Write-Host '==> Python dependencies (uv sync)'
& $uv sync | Out-Host

if ($Reseed -or -not (Test-Path 'data/processed/regions')) {
    Write-Host '==> seeding SYNTHETIC features at 200 m (Mars target). Add 60 m with: uv run pipeline seed-fake --scale 60'
    & $uv run pipeline seed-fake --scale 200 | Out-Host
}

if (-not $NoDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'docker not found. Install Docker Desktop, or run with -NoDocker'
    }
    $env:GIT_SHA = (git rev-parse HEAD)
    Write-Host '==> docker compose up (PostGIS, MinIO, API, frontend)'
    docker compose --env-file .env -f infra/docker-compose.yml up -d --build | Out-Host
    Write-Host '==> loading artifacts into PostGIS'
    $pw = (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=(.*)$').Matches[0].Groups[1].Value
    $env:DATABASE_URL = "postgresql+psycopg://eae:$pw@localhost:5432/eae"
    & $uv run pipeline load-db | Out-Host
    Write-Host 'API:      http://localhost:8000/docs'
    Write-Host 'App:      http://localhost:3000'
    Write-Host 'MinIO:    http://localhost:9001'
    return
}

Write-Host '==> starting API (memory store) on :8000 and frontend on :3000'
$token = (Select-String -Path .env -Pattern '^DEMO_TOKEN=(.*)$').Matches[0].Groups[1].Value
# Child processes inherit these (Start-Process -Environment needs PowerShell 7).
$env:EAE_STORE = 'memory'
$env:DEMO_TOKEN = $token
$api = Start-Process -PassThru -NoNewWindow -FilePath $uv -ArgumentList @(
    'run', 'uvicorn', 'backend.main:app', '--port', '8000', '--reload'
)
try {
    Push-Location frontend
    if (-not (Test-Path 'node_modules')) { npm install | Out-Host }
    $env:BACKEND_URL = 'http://localhost:8000'
    npm run dev
} finally {
    Pop-Location
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
}
