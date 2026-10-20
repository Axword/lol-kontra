#!/bin/bash
# Isolated GitHub runner only: never use this script on a real deployment.
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]] || {
    echo 'This smoke test is restricted to an ephemeral GitHub-hosted runner.' >&2; exit 1;
}
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
temporary=$(mktemp -d)
export RELEASE_SHA=ci
printf '%s' 'synthetic-ci-$NO_EXPANSION-#=+!*0123456789abcdefghijklm' > "$temporary/django-secret"
python3 "$root/infra/vps/configure.py" create --django-secret-file "$temporary/django-secret" --file "$temporary/app.env" \
    --domain game.example.com --email ci@example.com --postgres-major 18
mkdir -p "$temporary/backups"
sudo chown root:root "$temporary/backups"
sudo chmod 0700 "$temporary/backups"
# Test TLS and proxy routing without asking a public ACME service for a certificate.
sed -e '/email /a\	skip_install_trust' -e '/encode zstd gzip/a\	tls internal' "$root/infra/vps/Caddyfile" > "$temporary/Caddyfile"
cat > "$temporary/override.yaml" <<EOF
services:
  caddy:
    volumes:
      - $temporary/Caddyfile:/etc/caddy/Caddyfile:ro
  backup:
    volumes:
      - $temporary/backups:/backups
  backup-media:
    volumes:
      - $temporary/backups:/backups
EOF
compose() { docker compose -p words-v-ci --env-file "$temporary/app.env" -f "$root/compose.vps.yaml" -f "$temporary/override.yaml" --profile maintenance "$@"; }
cleanup() {
    compose down --volumes --remove-orphans >/dev/null
    # This is our own ephemeral runner directory, never a deployed backup.
    sudo chown -R "$(id -u):$(id -g)" "$temporary/backups"
    rm -rf -- "$temporary"
}
trap cleanup EXIT
compose build db api frontend
compose run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
compose up -d --wait --wait-timeout 180 db redis
compose run --rm --no-deps release
compose up -d --wait --wait-timeout 180 --no-deps api frontend
secret_hash=$(sha256sum "$temporary/django-secret" | cut -d' ' -f1)
compose exec -T -e "EXPECTED_SECRET_HASH=$secret_hash" api python -c 'import hashlib,os; assert hashlib.sha256(os.environ["DJANGO_SECRET_KEY"].encode()).hexdigest()==os.environ["EXPECTED_SECRET_HASH"]; print("PASS: literal identity secret preserved in runtime")'
compose up -d --no-deps caddy
for path in / /healthz/ /api/v1/dailies/today/ /admin/login/ /static/admin/css/base.css; do
    passed=0
    for _ in $(seq 1 20); do
        # Insecure is limited to this runner's disposable internal test CA.
        if curl --fail --silent --insecure --max-time 10 --resolve game.example.com:443:127.0.0.1 "https://game.example.com$path" >/dev/null; then
            passed=1; break
        fi
        sleep 2
    done
    [[ "$passed" == 1 ]] || { echo "Proxy check failed: $path"; exit 1; }
done
compose exec -T -e PROFILE_MIGRATION_SMOKE=create api python manage.py shell < "$root/infra/vps/profile-smoke.py"
compose run --rm --no-deps backup
compose run --rm --no-deps -e BACKUP_STAMP=ci backup-media
sudo test -s "$temporary/backups/media-ci.tar"
sudo chown -R "$(id -u):$(id -g)" "$temporary/backups"
dump=$(find "$temporary/backups" -maxdepth 1 -type f -name '*.dump' -print -quit)
[[ -n "$dump" && -s "$dump" ]]
compose exec -T db sh -ec 'createdb -U "$POSTGRES_USER" restore_ci'
compose exec -T db sh -ec 'pg_restore -U "$POSTGRES_USER" -d restore_ci --no-owner --no-acl --single-transaction --exit-on-error' < "$dump"
# Recreate the container to verify that PostgreSQL 18 writes to the named volume.
# A simple restart would not detect an accidental anonymous data volume.
compose up -d --wait --wait-timeout 180 --force-recreate --no-deps db
compose exec -T db sh -ec 'psql -U "$POSTGRES_USER" -d restore_ci --set=app_user="$POSTGRES_APP_USER" --set=owner_user="$POSTGRES_USER" --set=database_name=restore_ci -f /opt/grant-runtime.sql'
compose run --rm --no-deps -e POSTGRES_DB=restore_ci release python manage.py bootstrap_database
compose run --rm -T --no-deps -e POSTGRES_DB=restore_ci -e PROFILE_MIGRATION_SMOKE=check release python manage.py shell < "$root/infra/vps/profile-smoke.py"
compose exec -T db sh -ec 'dropdb -U "$POSTGRES_USER" restore_ci'
# Restart existing containers without running migrations again.
compose restart api frontend caddy
sleep 5
curl --fail --silent --insecure --retry 10 --retry-all-errors --retry-delay 2 --resolve game.example.com:443:127.0.0.1 https://game.example.com/healthz/ >/dev/null
echo 'PASS: production images, private Postgres, release checks, HTTPS routing, admin/static, dump restore and restart.'
