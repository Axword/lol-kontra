#!/bin/bash
# Read-only source export. Final export requires stopping old application writers.
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
check_env
service=/etc/words-v/neon.pg_service.conf
[[ -f "$service" && ! -L "$service" && $(stat -c %u "$service") == 0 && $(stat -c %a "$service") == 600 ]] || {
    echo 'Expected root-owned mode 0600 /etc/words-v/neon.pg_service.conf.' >&2; exit 1;
}
major=$(python3 - "$ENV_FILE" "$service" <<'PY'
import configparser, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
# app.env contains no executable code; only the checked version is read here.
app = Path(sys.argv[1]).read_text().splitlines()
major = next(line.partition('=')[2].strip("'") for line in app if line.startswith('POSTGRES_MAJOR='))
source = configparser.ConfigParser(interpolation=None)
source.read(sys.argv[2])
section = source['neon-export']
if ('-pooler' in section.get('host', '') or not section.get('host', '').endswith('.neon.tech')
        or section.get('sslmode') != 'verify-full'
        or section.get('sslrootcert') != '/etc/ssl/certs/ca-certificates.crt'):
    raise SystemExit('Use a direct Neon host with verify-full TLS and the container CA bundle.')
print(major)
PY
)
image="postgres:$major-alpine"
run_source() {
    docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs /tmp \
        --mount "type=bind,source=$service,target=/run/neon.pg_service.conf,readonly" \
        --env PGSERVICEFILE=/run/neon.pg_service.conf --env PGSERVICE=neon-export "$image" "$@"
}
version=$(run_source psql -X -Atc 'SHOW server_version_num')
[[ "$version" =~ ^[0-9]+$ && $((version / 10000)) == "$major" ]] || {
    echo 'Source PostgreSQL major differs from the target. Review versions before exporting/importing.' >&2; exit 1;
}
install -d -m 0700 /var/backups/words-v
dump="/var/backups/words-v/neon-$(date -u +%Y%m%dT%H%M%S)-${RANDOM}.dump"
temporary="$dump.incomplete"
trap 'rm -f -- "$temporary"' EXIT
run_source pg_dump --format=custom --no-owner --no-acl > "$temporary"
docker run --rm -i --read-only --cap-drop ALL "$image" pg_restore --list < "$temporary" >/dev/null
mv -- "$temporary" "$dump"
echo "Read-only Neon export completed: $dump"
