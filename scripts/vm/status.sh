#!/usr/bin/env bash
# Laptop. VM state, machine type, containers, disk use and public URL.
source "$(dirname "$0")/_lib.sh"
STATUS="$(vm_status)"
TYPE="$(gc compute instances describe "$VM_NAME" --zone "$ZONE" --format='value(machineType.basename())' 2>/dev/null || true)"
say "VM $VM_NAME: $STATUS $TYPE"
say "URL: https://$(public_hostname)"
if [[ "$STATUS" == "RUNNING" ]]; then
  vm_ssh "cd $APP_DIR && docker compose --env-file .env -f infra/docker-compose.prod.yml ps && df -h / | tail -1"
fi
