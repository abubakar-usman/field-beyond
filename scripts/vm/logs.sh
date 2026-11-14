#!/usr/bin/env bash
# Laptop. Tail container logs: scripts/vm/logs.sh [backend|frontend|db|caddy]
source "$(dirname "$0")/_lib.sh"
vm_ssh "cd $APP_DIR && docker compose --env-file .env -f infra/docker-compose.prod.yml logs -f --tail=200 ${1:-}"
