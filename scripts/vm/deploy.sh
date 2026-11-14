#!/usr/bin/env bash
# VM, every release. Deploys committed origin/main, migrates, health-checks, rolls back on failure.
source "$(dirname "$0")/_lib.sh"
cd "$APP_DIR"
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/eae_deploy -o StrictHostKeyChecking=accept-new"

say "fetching origin/main"
git fetch origin
git reset --hard origin/main
SHA="$(git rev-parse HEAD)"
HOST="$(grep '^PUBLIC_HOSTNAME=' .env | cut -d= -f2)"

for img in eae-backend eae-frontend; do
  if docker image inspect "$img:current" >/dev/null 2>&1; then
    docker tag "$img:current" "$img:previous"
  fi
done

say "building images for $SHA"
GIT_SHA="$SHA" IMAGE_TAG=current "${COMPOSE[@]}" build
say "running migrations"
IMAGE_TAG=current "${COMPOSE[@]}" run --rm backend alembic upgrade head
IMAGE_TAG=current "${COMPOSE[@]}" up -d

say "health check https://$HOST/api/health"
for _ in $(seq 1 30); do
  if curl -fsS "https://$HOST/api/health" >/dev/null 2>&1; then
    say "healthy: $SHA"
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 2
done

warn "health check failed; rolling back to the previous images"
for img in eae-backend eae-frontend; do
  if docker image inspect "$img:previous" >/dev/null 2>&1; then
    docker tag "$img:previous" "$img:current"
  fi
done
IMAGE_TAG=current "${COMPOSE[@]}" up -d
die "deploy of $SHA failed; previous images restored. Check: scripts/vm/logs.sh backend"
