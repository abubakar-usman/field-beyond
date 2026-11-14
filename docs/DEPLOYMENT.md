# Deployment (Google Cloud)

> Scripts are written (`scripts/vm/`, `scripts/local/`) to this spec but have **not been run against a real GCP project yet**. Keep this file in sync with them.

## Target setup

| Thing | Value (defaults in `scripts/vm/config.env`) |
|---|---|
| Project | `earth-analog-explorer` (owner creates it) |
| Region / zone | `us-central1` / `us-central1-a` |
| VM | `eae-vm`, e2-standard-4 (4 vCPU, 16 GB), Ubuntu 24.04 LTS, 200 GB balanced disk |
| Processing size | e2-standard-8 (temporary, during `process-region.sh`) |
| Bucket | `gs://<project-id>-eae-data`, Standard class, `us-central1`, uniform access |
| Service account | `eae-vm-sa`, role `roles/storage.objectAdmin` on the bucket only |
| Static IP | `eae-ip` |
| Firewall | 22 from the owner's IP only; 80 and 443 public |
| HTTPS | Caddy with automatic certificates; hostname `<ip-with-dashes>.sslip.io` or own domain |
| App | `infra/docker-compose.prod.yml`: `db` (postgis/postgis:16), `backend`, `frontend`, `caddy` |

## Cost (approx., Nov 2026 — confirm in the GCP Pricing Calculator)
- e2-standard-4: $0.134/h ≈ $98/month (≈ $3.20/day). e2-standard-8 ≈ $0.27/h.
- 200 GB balanced disk ≈ $20/month (charged even when VM is stopped).
- Cloud Storage Standard ≈ $0.020/GB-month → ≈ $1–2/month for 50–100 GB.
- **Hackathon week with VM stopped when idle: ≈ $5–15.** Set a $50 budget alert.

## Scripts

All bash scripts: `set -euo pipefail`, idempotent (check before create), print each action, source `scripts/vm/config.env`. Laptop scripts run in **Git Bash** on Windows (gcloud must be on PATH).

### `scripts/vm/config.env`
```bash
PROJECT_ID=earth-analog-explorer
REGION=us-central1
ZONE=us-central1-a
VM_NAME=eae-vm
VM_TYPE=e2-standard-4
VM_TYPE_PROCESSING=e2-standard-8
DISK_GB=200
BUCKET=gs://${PROJECT_ID}-eae-data
SA_NAME=eae-vm-sa
IP_NAME=eae-ip
REPO_SSH_URL=git@github.com:<owner>/<repo>.git
APP_DIR=/opt/eae
DOMAIN=            # empty → use <ip>.sslip.io
```

### `create-vm.sh` (laptop, once)
1. `gcloud config set project $PROJECT_ID`; enable `compute.googleapis.com`, `storage.googleapis.com`.
2. Create bucket if missing (`gcloud storage buckets create ... --uniform-bucket-level-access`).
3. Create service account if missing; grant bucket-level `roles/storage.objectAdmin`.
4. Reserve static IP if missing.
5. Firewall rules: `eae-allow-ssh` (tcp:22 from `$(curl -s ifconfig.me)/32`), `eae-allow-web` (tcp:80,443 from 0.0.0.0/0), target tag `eae`.
6. Create VM if missing: image family `ubuntu-2404-lts-amd64`, disk 200 GB pd-balanced, service account + `cloud-platform` scope, tag `eae`, static IP.
7. Print next step: `scripts/vm/ssh.sh` then run `bootstrap.sh` on the VM.

### `bootstrap.sh` (VM, once)
1. Install Docker Engine + Compose plugin from Docker's apt repo; add user to `docker` group.
2. Generate `~/.ssh/eae_deploy` key if missing; **print the public key** and pause: "Add this as a read-only Deploy key in GitHub, then press Enter."
3. Clone `$REPO_SSH_URL` into `$APP_DIR` (or `git pull` if present).
4. Create `$APP_DIR/.env` from `infra/.env.example` if missing, with random `POSTGRES_PASSWORD`, `DEMO_TOKEN` (`openssl rand -hex 24`), `PUBLIC_HOSTNAME` (domain or `<ip>.sslip.io`), `GCS_BUCKET`. `chmod 600`.
5. Install a nightly cron entry: `0 3 * * * $APP_DIR/scripts/vm/backup-db.sh`.
6. Run `deploy.sh`.

### `deploy.sh` (VM, every release)
1. `git fetch && git reset --hard origin/main` (deploy only committed code).
2. Tag current images as `:previous`.
3. `docker compose -f infra/docker-compose.prod.yml build`.
4. Run migrations: `docker compose ... run --rm backend alembic upgrade head`.
5. `docker compose ... up -d`.
6. Health check `https://$PUBLIC_HOSTNAME/api/health` up to 60 s; on failure retag `:previous`, `up -d`, exit 1.
7. `docker image prune -f`.

### `process-region.sh <region> <target>` (laptop)
1. Stop VM → `gcloud compute instances set-machine-type ... $VM_TYPE_PROCESSING` → start. (Brief downtime — fine for a hackathon.)
2. SSH: `docker compose ... run --rm backend uv run pipeline run --region $1 --target $2`.
3. SSH: sync outputs to `$BUCKET/derived/` (`gcloud storage rsync`).
4. Stop → resize back to `$VM_TYPE` → start → `deploy.sh` health check.
5. Always resize back, even on failure (`trap`).

### `backup-db.sh` (VM, cron) / `restore-db.sh <file>` (VM)
- Backup: `pg_dump -Fc` inside the db container → gzip → `$BUCKET/backups/eae-YYYYMMDD-HHMM.dump.gz`; delete all but the newest 7.
- Restore: download chosen file, confirm prompt, `pg_restore --clean --if-exists`.

### Laptop helpers
| Script | Does |
|---|---|
| `start.sh` / `stop.sh` | `gcloud compute instances start/stop $VM_NAME` |
| `status.sh` | VM status, `docker compose ps` over SSH, `df -h`, public URL |
| `logs.sh [service]` | `docker compose logs -f --tail=200 [service]` over SSH |
| `ssh.sh` | `gcloud compute ssh $VM_NAME --zone $ZONE` |

### Local (Windows PowerShell)
| Script | Does |
|---|---|
| `scripts/local/check-tools.ps1` | Checks git, uv, node, docker, gcloud, free disk (warn < 40 GB), virtualization; prints `winget` commands for anything missing |
| `scripts/local/dev.ps1` | `docker compose -f infra/docker-compose.yml up -d`, `uv run alembic upgrade head`, `uv run pipeline seed-fake`, starts frontend dev server |

## Recovery cheatsheet
| Problem | Fix |
|---|---|
| Site down after deploy | `deploy.sh` auto-rolls back; check `logs.sh backend` |
| HTTPS certificate fails | Port 80 must be open; check `DOMAIN`/sslip hostname resolves to the static IP; `logs.sh caddy` |
| Disk full | `docker system prune`; delete raw DEMs already copied to the bucket |
| VM stuck on e2-standard-8 | Run `stop.sh`, `gcloud compute instances set-machine-type ... e2-standard-4`, `start.sh` |
| Lost DB | `restore-db.sh` with the newest backup |
| SSH refused | Your IP changed → re-run `create-vm.sh` (updates the firewall rule) |

## Security notes
- `.env` never committed; `chmod 600`.
- Postgres not exposed outside the Docker network.
- Review/processing endpoints require `DEMO_TOKEN` header.
- VM service account has bucket access only.
