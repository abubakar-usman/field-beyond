# Start the app locally on Windows.
#   powershell -ExecutionPolicy Bypass -File scripts\local\dev.ps1            # Docker (same as scripts\docker\up.ps1)
#   powershell -ExecutionPolicy Bypass -File scripts\local\dev.ps1 -NoDocker  # no Docker: uv + npm dev servers, in-memory store
#   powershell -ExecutionPolicy Bypass -File scripts\local\dev.ps1 -NoDocker -Moon  # also seed Moon-scale data
# Both modes seed SYNTHETIC features first if none exist (pipeline seed-fake).
param(
    [switch]$NoDocker,
    [switch]$Moon,
    [switch]$Reseed
)
$ErrorActionPreference = 'Continue'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $Root

if (-not $NoDocker) {
    $fwd = @{}
    if ($Reseed) { $fwd['Reseed'] = $true }
    if ($Moon) { $fwd['Moon'] = $true }
    & (Join-Path $Root 'scripts\docker\up.ps1') @fwd
    exit $LASTEXITCODE
}

function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $wg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($wg) { return $wg.FullName }
    Write-Host 'uv not found: winget install astral-sh.uv' -ForegroundColor Red
    exit 1
}
$uv = Find-Uv

function New-Secret {
    $bytes = New-Object byte[] 24
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

if (-not (Test-Path '.env')) {
    Write-Host '==> writing .env with random local secrets'
    $lines = Get-Content 'infra/.env.example' | ForEach-Object {
        $_ -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$(New-Secret)" `
           -replace '^DEMO_TOKEN=.*', "DEMO_TOKEN=$(New-Secret)" `
           -replace '^MINIO_ROOT_PASSWORD=.*', "MINIO_ROOT_PASSWORD=$(New-Secret)"
    }
    [System.IO.File]::WriteAllLines((Join-Path $Root '.env'), $lines, (New-Object System.Text.UTF8Encoding($false)))
}

Write-Host '==> Python dependencies (uv sync)'
& $uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Reseed -or -not (Test-Path 'data/processed/regions')) {
    Write-Host '==> seeding SYNTHETIC features at 200 m (Mars target)'
    & $uv run pipeline seed-fake --scale 200
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($Moon -and ($Reseed -or -not (Test-Path 'data/processed/regions/earth_sahara/current-60m.json'))) {
    Write-Host '==> seeding SYNTHETIC features at 60 m (Moon target)'
    & $uv run pipeline seed-fake --scale 60
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
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
    if (-not (Test-Path 'node_modules')) { npm install }
    $env:BACKEND_URL = 'http://localhost:8000'
    npm run dev
} finally {
    Pop-Location
    Stop-Process -Id $api.Id -ErrorAction SilentlyContinue
}
