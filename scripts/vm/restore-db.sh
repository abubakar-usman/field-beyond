#!/usr/bin/env bash
# VM. Restore a backup:
#   scripts/vm/restore-db.sh gs://<bucket>/backups/eae-YYYYMMDD-HHMM.dump.gz
source "$(dirname "$0")/_lib.sh"
SRC="${1:?usage: restore-db.sh <gs://bucket/backups/file.dump.gz>}"

read -r -p "This replaces the current database with $SRC. Type restore to continue: " ok
[[ "$ok" == "restore" ]] || die "cancelled"

gcloud storage cp "$SRC" /tmp/restore.dump.gz
gunzip -c /tmp/restore.dump.gz | "${COMPOSE[@]}" exec -T db pg_restore -U eae -d eae --clean --if-exists
rm -f /tmp/restore.dump.gz
say "restored from $SRC"
