# Local setup

The project laptop in the decisions is Windows. This checkout is also opened on Linux. Use the section that matches the machine in front of you.

## Linux (bash)
Install `uv`, Docker Engine with the Compose plugin, Node.js, and the Google Cloud CLI from their own docs (no winget, no WSL). Python for the project is still 3.12 via `uv`, whatever the system Python is. VM scripts in `scripts/vm/` run in bash. `scripts/local/*.ps1` is for the Windows laptop.

## Windows laptop (checked 2026-11-14)
Intel Core i7-8565U (4 cores / 8 threads) · 15.8 GB RAM · Windows 11 Pro · **64 GB free on C:** · Windows reports CPU virtualization as **disabled**.

## Tool status

| Tool | Status | Action |
|---|---|---|
| Git 2.54 | ✅ | — |
| Node.js 24 + npm 12 | ✅ | — |
| VS Code 1.145 | ✅ | — |
| curl, OpenSSH | ✅ | — |
| Python 3.14 | ✅ but too new | Don't use directly; `uv` installs Python 3.12 for the project |
| uv | ✅ 0.13.8 (installed 2026-11-14; Python 3.12.16 via uv) | — |
| WSL2 | ❌ | `wsl --install` in an **admin** terminal, then restart |
| Docker Desktop | ❌ | `winget install Docker.DockerDesktop` (after WSL2). Free for personal, education and small teams |
| Google Cloud CLI | ❌ | `winget install Google.CloudSDK`, then `gcloud auth login` |
| GDAL, psql | ❌ | Not needed on the laptop (inside Docker / rasterio wheels) |
| AWS CLI | ❌ | Not needed (`AWS_NO_SIGN_REQUEST=YES` with rasterio) |
| make | ❌ | Not needed (PowerShell/bash scripts) |
| pnpm | ❌ | Optional; npm is fine |

## Install order
1. Admin terminal:
   ```bash
   wsl --install
   ```
   Restart. If WSL or Docker later complains about virtualization, enable **Intel VT-x** in the BIOS/UEFI (usually under Advanced → CPU Configuration) and restart.
2. ```bash
   winget install astral-sh.uv
   ```
3. ```bash
   winget install Docker.DockerDesktop
   ```
   Start Docker Desktop once and accept its terms (manual).
4. ```bash
   winget install Google.CloudSDK
   ```
5. Open a new terminal and verify:
   ```bash
   uv --version
   ```
   ```bash
   docker compose version
   ```
   ```bash
   gcloud --version
   ```

## Disk space
Docker images (~5–10 GB) plus planetary DEMs (~22 GB) won't fit comfortably in 64 GB. Keep only small sample crops locally (`data/samples/`, gitignored); full downloads and processing happen on the GCP VM.

## Shells
- **PowerShell** for `scripts/local/*.ps1`.
- **Git Bash** for `scripts/vm/*.sh` (they call `gcloud`).
