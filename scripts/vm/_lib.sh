#!/usr/bin/env bash
# Shared helpers. Sourced by the other scripts; not run directly.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.env
source "$SCRIPT_DIR/config.env"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
COMPOSE=(docker compose --env-file "$APP_DIR/.env" -f "$APP_DIR/infra/docker-compose.prod.yml")

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is not installed or not on PATH"; }

gc() { gcloud --project "$PROJECT_ID" "$@"; }
vm_ssh() { gc compute ssh "$VM_NAME" --zone "$ZONE" --command "$*"; }
vm_status() { gc compute instances describe "$VM_NAME" --zone "$ZONE" --format='value(status)' 2>/dev/null || echo MISSING; }
static_ip() { gc compute addresses describe "$IP_NAME" --region "$REGION" --format='value(address)' 2>/dev/null || true; }
public_hostname() {
  if [[ -n "${DOMAIN// /}" ]]; then
    echo "$DOMAIN"
  else
    local ip
    ip="$(static_ip)"
    echo "${ip//./-}.sslip.io"
  fi
}
