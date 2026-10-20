#!/bin/bash
# Logical recovery files for the daily full-server backup managed by OVH.
# This does not replace or report success for the separate restic offsite gate.
set -euo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
release=$(readlink -f /opt/words-v/current)
[[ "$release" =~ ^/opt/words-v/releases/[0-9a-f]{40}$ ]] || { echo 'Expected an immutable current release.' >&2; exit 1; }
source "$release/infra/vps/common.sh"
check_env
exec 9>/run/lock/words-v-backup.lock
flock -n 9 || { echo 'Another backup is in progress.' >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%S%NZ)
before=$(find /var/backups/words-v -maxdepth 1 -type f -name 'worlds-xi-*.dump' -printf '%f\n' | sort)
compose --profile maintenance run --rm --no-deps backup
after=$(find /var/backups/words-v -maxdepth 1 -type f -name 'worlds-xi-*.dump' -printf '%f\n' | sort)
dump=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after"))
[[ "$dump" =~ ^worlds-xi-[0-9TZ]+\.dump$ ]] || { echo 'Expected exactly one completed dump.' >&2; exit 1; }
compose exec -T db pg_restore --file=/dev/null < "/var/backups/words-v/$dump"
compose --profile maintenance run --rm --no-deps -e "BACKUP_STAMP=$stamp" backup-media
tar -cf "/var/backups/words-v/configuration-$stamp.tar" -C /etc/words-v app.env
python3 - "$dump" "$stamp" "$RELEASE_SHA" <<'PY'
import hashlib,json,pathlib,sys
root=pathlib.Path('/var/backups/words-v')
dump,stamp,release=sys.argv[1:]
names=[dump,f'media-{stamp}.tar',f'configuration-{stamp}.tar']
files={name:{'bytes':(root/name).stat().st_size,'sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()} for name in names}
report={'release':release,'created_at_utc':stamp,'files':files,'archive_blocks_verified':True}
(root/'latest-local-backup.json').write_text(json.dumps(report,indent=2)+'\n')
print('Local recovery files verified. OVH manages the independent full-server backup; restic offsite remains separately configured.')
PY
