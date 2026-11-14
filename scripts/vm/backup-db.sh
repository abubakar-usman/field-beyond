#!/usr/bin/env bash
# VM (nightly cron). pg_dump -> gzip -> bucket; keep the newest 7.
source "$(dirname "$0")/_lib.sh"
STAMP="$(date -u +%Y%m%d-%H%M)"
FILE="/tmp/eae-$STAMP.dump.gz"

say "dumping database"
"${COMPOSE[@]}" exec -T db pg_dump -U eae -Fc eae | gzip >"$FILE"
gcloud storage cp "$FILE" "$BUCKET/backups/"
rm -f "$FILE"

mapfile -t OLD < <(gcloud storage ls "$BUCKET/backups/eae-*.dump.gz" | sort | head -n -7)
for f in "${OLD[@]}"; do
  say "deleting old backup $f"
  gcloud storage rm "$f"
done
say "backup $STAMP stored"
