#!/usr/bin/env bash
# VM, once. Installs Docker, clones the repo, writes .env with random secrets,
# installs the nightly backup, then deploys.
source "$(dirname "$0")/_lib.sh"

if ! command -v docker >/dev/null 2>&1; then
  say "installing Docker Engine and the Compose plugin"
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl openssl
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CODENAME stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  warn "log out and back in so the docker group applies, then run this script again"
  exit 0
fi

KEY="$HOME/.ssh/eae_deploy"
if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -N "" -f "$KEY" -C "eae-vm-deploy"
  say "add this public key as a READ-ONLY deploy key on GitHub, then press Enter:"
  cat "$KEY.pub"
  read -r _
fi
export GIT_SSH_COMMAND="ssh -i $KEY -o StrictHostKeyChecking=accept-new"

sudo mkdir -p "$APP_DIR"
sudo chown "$USER" "$APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  say "repo present, pulling"
  git -C "$APP_DIR" pull --ff-only
else
  say "cloning $REPO_SSH_URL"
  git clone "$REPO_SSH_URL" "$APP_DIR"
fi
# The backend container runs as uid 1000 and writes pipeline outputs here.
mkdir -p "$APP_DIR/data"
sudo chown -R 1000:1000 "$APP_DIR/data"

if [[ ! -f "$APP_DIR/.env" ]]; then
  say "writing $APP_DIR/.env with random secrets"
  IP="$(curl -fsS -H 'Metadata-Flavor: Google' \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)"
  HOST="${DOMAIN// /}"
  if [[ -z "$HOST" ]]; then HOST="${IP//./-}.sslip.io"; fi
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
    -e "s|^DEMO_TOKEN=.*|DEMO_TOKEN=$(openssl rand -hex 24)|" \
    -e "s|^PUBLIC_HOSTNAME=.*|PUBLIC_HOSTNAME=$HOST|" \
    -e "s|^GCS_BUCKET=.*|GCS_BUCKET=${BUCKET#gs://}|" \
    "$APP_DIR/infra/.env.example" >"$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi

CRON="0 3 * * * $APP_DIR/scripts/vm/backup-db.sh >> $HOME/eae-backup.log 2>&1"
(crontab -l 2>/dev/null | grep -Fv "backup-db.sh" || true; echo "$CRON") | crontab -
say "nightly backup installed"

"$APP_DIR/scripts/vm/deploy.sh"
