#!/usr/bin/env bash
# Laptop. Resize the VM up, compute real features for <region> at <target>'s scale,
# load them into PostGIS, push artifacts to the bucket, and always resize back down.
#   scripts/vm/process-region.sh earth_sahara mars_jezero
source "$(dirname "$0")/_lib.sh"
need gcloud
REGION_ID="${1:?usage: process-region.sh <region_id> <target_id>}"
TARGET_ID="${2:?usage: process-region.sh <region_id> <target_id>}"

resize() {
  say "resizing $VM_NAME to $1"
  gc compute instances stop "$VM_NAME" --zone "$ZONE"
  gc compute instances set-machine-type "$VM_NAME" --zone "$ZONE" --machine-type "$1"
  gc compute instances start "$VM_NAME" --zone "$ZONE"
}

cleanup() {
  local rc=$?
  resize "$VM_TYPE" || warn "could not resize back; do it by hand (docs/DEPLOYMENT.md recovery table)"
  sleep 20
  vm_ssh "$APP_DIR/scripts/vm/deploy.sh" || warn "post-resize deploy reported a problem"
  exit "$rc"
}
trap cleanup EXIT

resize "$VM_TYPE_PROCESSING"
sleep 20
RUN="cd $APP_DIR && docker compose --env-file .env -f infra/docker-compose.prod.yml run --rm backend"
vm_ssh "$RUN pipeline run --region $REGION_ID --target $TARGET_ID"
vm_ssh "$RUN pipeline load-db"
vm_ssh "$RUN pipeline push"
say "done: $REGION_ID for $TARGET_ID"
