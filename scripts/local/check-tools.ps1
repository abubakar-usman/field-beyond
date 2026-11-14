# Checks the laptop tools from docs/LOCAL_SETUP.md and prints install commands for anything missing.
#   powershell -File scripts/local/check-tools.ps1
$ErrorActionPreference = 'Continue'

function Test-Tool($name, $cmd, $install) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $found -and $name -eq 'uv') {
        $wg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($wg) { $found = $wg }
    }
    if ($found) {
        Write-Host ("[ok]      {0,-10} {1}" -f $name, ($found.Source, $found.FullName | Where-Object { $_ } | Select-Object -First 1))
    } else {
        Write-Host ("[missing] {0,-10} install: {1}" -f $name, $install) -ForegroundColor Yellow
    }
}

Test-Tool 'git'    'git'    'winget install Git.Git'
Test-Tool 'uv'     'uv'     'winget install astral-sh.uv'
Test-Tool 'node'   'node'   'winget install OpenJS.NodeJS.LTS'
Test-Tool 'npm'    'npm'    '(comes with Node.js)'
Test-Tool 'docker' 'docker' 'wsl --install (admin, restart), then winget install Docker.DockerDesktop'
Test-Tool 'gcloud' 'gcloud' 'winget install Google.CloudSDK, then gcloud auth login'

$drive = Get-PSDrive -Name ((Get-Location).Drive.Name)
$freeGB = [math]::Round($drive.Free / 1GB, 1)
if ($freeGB -lt 40) {
    Write-Host "[warn]    disk       $freeGB GB free (under 40 GB; keep full DEMs on the VM)" -ForegroundColor Yellow
} else {
    Write-Host "[ok]      disk       $freeGB GB free"
}

try {
    $virt = (Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled
    if ($virt) { Write-Host '[ok]      virt.      CPU virtualization enabled' }
    else { Write-Host '[warn]    virt.      CPU virtualization disabled in firmware (needed for WSL2/Docker): enable VT-x in BIOS' -ForegroundColor Yellow }
} catch {
    Write-Host '[?]       virt.      could not read virtualization state'
}

Write-Host ''
Write-Host 'Without Docker you can still run the app: powershell -File scripts/local/dev.ps1 -NoDocker'
