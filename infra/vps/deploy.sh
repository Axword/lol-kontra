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
    trap 'if [[ -n "${stage:-}" && "$stage" == "$root/releases/.staging-$sha-"* ]]; then rm -rf -- "$stage"; fi' EXIT
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
compose stop api worker beat
python3 "$SCRIPT_DIR/backup.py" --release "$RELEASE_DIR"
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
echo "Deployment healthy: $sha"
