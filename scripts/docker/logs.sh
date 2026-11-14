#!/usr/bin/env bash
# Follow container logs: scripts/docker/logs.sh [backend|frontend|db]
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose --env-file .env -f infra/docker-compose.yml logs -f --tail=200 "$@"
