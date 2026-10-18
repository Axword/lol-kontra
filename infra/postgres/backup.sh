#!/bin/sh
set -eu
umask 077

: "${POSTGRES_USER:?Set POSTGRES_USER}"
: "${POSTGRES_DB:?Set POSTGRES_DB}"
mkdir -p /backups
target="/backups/worlds-xi-$(date -u +%Y%m%dT%H%M%SZ).dump"
test ! -e "$target"
temporary="$target.incomplete"
trap 'rm -f "$temporary"' EXIT HUP INT TERM

pg_dump --host="${POSTGRES_HOST:-db}" --port="${POSTGRES_PORT:-5432}" \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" \
  --format=custom --no-owner --file="$temporary"
pg_restore --list "$temporary" >/dev/null
mv "$temporary" "$target"
printf 'Backup saved: %s\n' "$target"
