#!/bin/bash
set -euo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
sha=${1:-}
mode=${2:-}
[[ $# -le 2 && "$sha" =~ ^[a-f0-9]{40}$ && ( -z "$mode" || "$mode" == --rollback ) ]] || {
    echo 'Usage: words-v-deploy FULL_COMMIT_SHA [--rollback]' >&2; exit 1;
}
root=/opt/words-v
repo="$root/repository.git"
previous=$(readlink -f "$root/current" 2>/dev/null || true)
maintenance_started=0
recover_previous() {
    result=$?
    trap - EXIT
    if [[ -n "${stage:-}" && "$stage" == "$root/releases/.staging-$sha-"* ]]; then
        rm -rf -- "$stage"
    fi
    if (( result != 0 && maintenance_started == 1 )) && [[ "$previous" =~ ^/opt/words-v/releases/[a-f0-9]{40}$ ]]; then
        echo 'Deployment failed; restoring the previous application containers. Database migrations are retained.' >&2
        (
            export RELEASE_SHA=${previous##*/}
            source "$previous/infra/vps/common.sh"
            compose up -d --wait --wait-timeout 180 --no-deps api worker beat frontend caddy
            ln -sfn "$previous" "$root/.current-recovery"
            mv -Tf "$root/.current-recovery" "$root/current"
        ) || echo 'Previous containers require manual inspection.' >&2
    fi
    exit "$result"
}
trap recover_previous EXIT
exec 9>/run/lock/words-v-deploy.lock
flock -n 9 || { echo 'Another deployment is in progress.' >&2; exit 1; }
[[ -d "$repo" ]] || { echo 'Provision the repository first.' >&2; exit 1; }
git --git-dir="$repo" fetch --prune origin '+refs/heads/master:refs/remotes/origin/master'
git --git-dir="$repo" cat-file -e "$sha^{commit}"
git --git-dir="$repo" merge-base --is-ancestor "$sha" refs/remotes/origin/master
if [[ "$mode" != --rollback ]]; then
    [[ "$sha" == $(git --git-dir="$repo" rev-parse refs/remotes/origin/master) ]] || {
        echo 'Outdated deployment skipped: master already contains a newer commit.' >&2; exit 1;
    }
else
    [[ -f "$root/releases/$sha/.deployed-success" ]] || { echo 'Rollback requires a previously healthy release.' >&2; exit 1; }
fi
release="$root/releases/$sha"
if [[ ! -d "$release" ]]; then
    stage=$(mktemp -d "$root/releases/.staging-$sha-XXXXXX")
    git --git-dir="$repo" archive "$sha" | tar --no-same-owner --same-permissions -x -C "$stage"
    chmod 0755 "$stage"
    mv -- "$stage" "$release"
    stage=''
fi
# Always use the verified release archive, not a writable development checkout.
source "$release/infra/vps/common.sh"
export RELEASE_SHA="$sha"
check_env
compose config --quiet
compose build --pull db api frontend
compose up -d --wait --wait-timeout 120 db redis
backup_mode=restic
backup_mode_file=/etc/words-v/deploy-backup-mode
if [[ -e "$backup_mode_file" ]]; then
    [[ ! -L "$backup_mode_file" && $(stat -c %u "$backup_mode_file") == 0 && $(stat -c %a "$backup_mode_file") == 600 ]] || {
        echo 'Expected a root-owned mode 0600 deploy-backup-mode file.' >&2; exit 1;
    }
    backup_mode=$(cat "$backup_mode_file")
fi
case "$backup_mode" in
    restic) python3 "$SCRIPT_DIR/backup.py" --release "$RELEASE_DIR" ;;
    ovh-managed) systemctl start words-v-local-backup.service ;;
    *) echo 'Unknown deployment backup mode.' >&2; exit 1 ;;
esac
maintenance_started=1
compose stop api worker beat
if [[ "$mode" != --rollback ]]; then
    compose run --rm --no-deps release
fi
# Recreate release explicitly above. Do not accidentally rerun it as a dependency.
compose up -d --no-deps api worker beat frontend
compose up -d --no-deps caddy
domain=$(python3 "$SCRIPT_DIR/configure.py" domain --file "$ENV_FILE")
healthy=0
for _ in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 10 "https://$domain/healthz/" >/dev/null \
        && curl --fail --silent --show-error --max-time 10 "https://$domain/" >/dev/null \
        && curl --fail --silent --show-error --max-time 10 "https://$domain/api/v1/dailies/today/" >/dev/null; then
        healthy=1; break
    fi
    sleep 4
done
[[ "$healthy" == 1 ]] || { echo 'Health checks failed. Current release pointer was not changed; inspect services before retry/rollback.' >&2; exit 1; }
ln -sfn "$release" "$root/.current-next"
mv -Tf "$root/.current-next" "$root/current"
touch "$release/.deployed-success"
# Atomic replacement also updates the deployment tool for subsequent releases.
install -m 0755 "$release/infra/vps/deploy.sh" /usr/local/sbin/.words-v-deploy-next
mv -f /usr/local/sbin/.words-v-deploy-next /usr/local/sbin/words-v-deploy
if [[ -f "$release/infra/vps/deploy-command.sh" ]]; then
    install -m 0755 "$release/infra/vps/deploy-command.sh" /usr/local/sbin/.words-v-deploy-command-next
    mv -f /usr/local/sbin/.words-v-deploy-command-next /usr/local/sbin/words-v-deploy-command
fi
maintenance_started=0
echo "Deployment healthy: $sha"
