---
name: run-app
description: Use when starting, testing, deploying or debugging the Earth Analog Explorer app — locally on the Windows laptop or on the Google Cloud VM.
---

# Running Earth Analog Explorer

> Commands below are the planned interface. If a script doesn't exist yet, build it to match `docs/DEPLOYMENT.md`.

## Local (Windows laptop)
- Check tools: `powershell -File scripts/local/check-tools.ps1`
- Start everything: `powershell -File scripts/local/dev.ps1` (Docker Compose up, migrations, fake seed data, frontend dev server)
- Python deps: `uv sync`; run tests: `uv run pytest`; lint: `uv run ruff check .`; types: `uv run mypy core backend pipeline`
- Frontend: `cd frontend && npm install && npm run dev` → http://localhost:3000
- API docs: http://localhost:8000/docs
- Use Python 3.12 via uv only — never the system Python 3.14.
- Don't download full planetary DEMs locally (disk is tight). Use `data/samples/` crops or `pipeline seed-fake`.

## Google Cloud VM (run from Git Bash on the laptop)
| Need | Command |
|---|---|
| Start / stop VM | `scripts/vm/start.sh` / `scripts/vm/stop.sh` |
| Status + URL | `scripts/vm/status.sh` |
| Logs | `scripts/vm/logs.sh backend` |
| Shell | `scripts/vm/ssh.sh` |
| Deploy latest `main` | `scripts/vm/ssh.sh` then `/opt/eae/scripts/vm/deploy.sh` |
| Process a region | `scripts/vm/process-region.sh earth_sahara mars_jezero` |
| Backup DB now | on VM: `/opt/eae/scripts/vm/backup-db.sh` |

## Rules
- Creating VMs, buckets or IPs costs money: confirm with the owner before running `create-vm.sh` or resizing.
- Remind the owner to stop the VM when idle.
- Never print or commit `.env` contents.
- After deploying, check `https://<host>/api/health`.
