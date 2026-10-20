#!/bin/bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
check_env
dump=$(realpath -e -- "${1:?Provide a local custom-format dump in /var/backups/words-v}")
[[ "$dump" == /var/backups/words-v/*.dump ]] || { echo 'Unexpected backup path.' >&2; exit 1; }
test_db="restore_check_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
created=0
cleanup() {
    if [[ "$created" == 1 && "$test_db" =~ ^restore_check_[0-9]+_[0-9]+$ ]]; then
        compose exec -T db /bin/sh -ec 'dropdb --username="$POSTGRES_USER" "$1"' sh "$test_db"
    fi
}
trap cleanup EXIT
compose exec -T db /bin/sh -ec 'createdb --username="$POSTGRES_USER" --template=template0 "$1"' sh "$test_db"
created=1
compose exec -T db /bin/sh -ec 'pg_restore --username="$POSTGRES_USER" --dbname="$1" --no-owner --no-acl --single-transaction --exit-on-error' sh "$test_db" < "$dump"
compose exec -T db /bin/sh -ec 'psql --username="$POSTGRES_USER" --dbname="$1" --set=app_user="$POSTGRES_APP_USER" --set=owner_user="$POSTGRES_USER" --set=database_name="$1" -f /opt/grant-runtime.sql' sh "$test_db"
compose run --rm --no-deps -e "POSTGRES_DB=$test_db" release python manage.py bootstrap_database
echo 'Restore and application data checks passed in a separate temporary database.'
