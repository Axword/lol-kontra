#!/bin/bash
# First import only. Never overwrites a populated application database.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
check_env
exec 9>/run/lock/words-v-deploy.lock
flock -n 9 || { echo 'Another deployment or import is in progress.' >&2; exit 1; }
dump=$(realpath -e -- "${1:?Provide a custom-format pg_dump file in /var/backups/words-v}")
[[ "$dump" == /var/backups/words-v/*.dump ]] || { echo 'Unexpected backup path.' >&2; exit 1; }
running=$(compose ps --status running --services)
if grep -Eq '^(api|worker|beat)$' <<< "$running"; then
    echo 'Import requires application writers to be stopped.' >&2; exit 1
fi
count=$(compose exec -T db /bin/sh -ec 'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname=\$\$public\$\$"')
[[ "$count" == 0 ]] || { echo 'Refusing import: target public schema is not empty.' >&2; exit 1; }
compose exec -T db /bin/sh -ec 'pg_restore --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --no-owner --no-acl --single-transaction --exit-on-error' < "$dump"
compose exec -T db /bin/sh -ec 'psql --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --set=app_user="$POSTGRES_APP_USER" --set=owner_user="$POSTGRES_USER" --set=database_name="$POSTGRES_DB" -f /opt/grant-runtime.sql'
echo 'Import completed. Run the release/deployment checks before changing DNS.'
