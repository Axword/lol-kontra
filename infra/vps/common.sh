#!/bin/bash
# Source only from the trusted release, never from request input.
set -euo pipefail
umask 077
APP_ROOT=/opt/words-v
ENV_FILE=/etc/words-v/app.env
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
RELEASE_DIR=$(cd -- "$SCRIPT_DIR/../.." && pwd -P)
export RELEASE_SHA=${RELEASE_SHA:-$(basename "$RELEASE_DIR")}
require_root() { [[ $(id -u) == 0 ]] || { echo 'Run this command with sudo.' >&2; exit 1; }; }
compose() { docker compose --project-name words-v --env-file "$ENV_FILE" -f "$RELEASE_DIR/compose.vps.yaml" "$@"; }
check_env() {
    require_root
    [[ -f "$ENV_FILE" && ! -L "$ENV_FILE" && $(stat -c %u "$ENV_FILE") == 0 && $(stat -c %a "$ENV_FILE") == 600 ]] || {
        echo 'Expected a root-owned, mode 0600 /etc/words-v/app.env.' >&2; exit 1;
    }
    python3 "$SCRIPT_DIR/configure.py" check --file "$ENV_FILE"
}
