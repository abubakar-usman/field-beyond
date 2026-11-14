#!/usr/bin/env bash
# Stop the app.
#   scripts/docker/down.sh          # stop containers, keep the database and data
#   scripts/docker/down.sh --wipe   # also delete the database and pipeline data volumes
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ -f .env ]] || { echo "no .env: nothing was started from this folder"; exit 0; }
DC=(docker compose --env-file .env -f infra/docker-compose.yml --profile storage)
if [[ "${1:-}" == "--wipe" ]]; then
  "${DC[@]}" down -v
  echo "stopped and deleted volumes (database, pipeline data, MinIO)"
else
  "${DC[@]}" down
  echo "stopped (data kept; use --wipe to delete it)"
fi
