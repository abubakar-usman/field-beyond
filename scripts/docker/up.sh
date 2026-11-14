#!/usr/bin/env bash
# Build the Docker images, start the app, seed SYNTHETIC demo data and load it into PostGIS.
# Needs only Docker (with the Compose v2 plugin) and git. Run from anywhere:
#   scripts/docker/up.sh             # Mars target data (200 m), about 3-5 min the first time
#   scripts/docker/up.sh --moon      # also 60 m data for the Moon target (about 15 min more)
#   scripts/docker/up.sh --no-seed   # build and start only
#   scripts/docker/up.sh --reseed    # regenerate the synthetic data
#   scripts/docker/up.sh --storage   # also start MinIO (object storage, optional)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

SEED=1
MOON=0
RESEED=0
PROFILE=()
for arg in "$@"; do
  case "$arg" in
    --no-seed) SEED=0 ;;
    --moon) MOON=1 ;;
    --reseed) RESEED=1 ;;
    --storage) PROFILE=(--profile storage) ;;
    -h | --help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg (see --help)" >&2; exit 2 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "the Docker Compose v2 plugin ('docker compose') is required"
docker info >/dev/null 2>&1 || die "the Docker daemon is not running (start Docker Desktop / dockerd)"

secret() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 24
  else head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}

if [[ ! -f .env ]]; then
  say "creating .env with random local secrets"
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret)|" \
    -e "s|^DEMO_TOKEN=.*|DEMO_TOKEN=$(secret)|" \
    -e "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$(secret)|" \
    infra/.env.example >.env
  chmod 600 .env
fi

GIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
export GIT_SHA
DC=(docker compose --env-file .env -f infra/docker-compose.yml ${PROFILE[@]+"${PROFILE[@]}"})

say "building images (first build downloads base images and dependencies)"
"${DC[@]}" build

say "starting containers"
"${DC[@]}" up -d

say "waiting for the API (migrations run first)"
ok=0
for _ in $(seq 1 60); do
  if "${DC[@]}" exec -T backend python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" != 1 ]]; then
  "${DC[@]}" logs --tail=60 backend
  die "the API did not become healthy; backend logs are above"
fi

has() { "${DC[@]}" exec -T backend test -f "/data/processed/regions/earth_sahara/current-$1m.json"; }

if [[ "$SEED" == 1 ]]; then
  if [[ "$RESEED" == 1 ]] || ! has 200; then
    say "seeding SYNTHETIC 200 m features (Mars target), about 2-4 min"
    "${DC[@]}" exec -T backend pipeline seed-fake --scale 200
  else
    say "200 m data already present (use --reseed to regenerate)"
  fi
  if [[ "$MOON" == 1 ]] && { [[ "$RESEED" == 1 ]] || ! has 60; }; then
    say "seeding SYNTHETIC 60 m features (Moon target), about 15 min"
    "${DC[@]}" exec -T backend pipeline seed-fake --scale 60
  fi
  say "loading data into PostGIS"
  "${DC[@]}" exec -T backend pipeline load-db
fi

API_PORT="$(grep -E '^API_PORT=' .env | cut -d= -f2 || true)"
APP_PORT="$(grep -E '^APP_PORT=' .env | cut -d= -f2 || true)"
say "ready"
echo "  App:       http://localhost:${APP_PORT:-3000}"
echo "  API docs:  http://localhost:${API_PORT:-8000}/docs"
echo "  Health:    http://localhost:${API_PORT:-8000}/health"
echo "  Reviews need the DEMO_TOKEN value from .env"
echo "  Stop:      scripts/docker/down.sh    Logs: scripts/docker/logs.sh [backend|frontend|db]"
