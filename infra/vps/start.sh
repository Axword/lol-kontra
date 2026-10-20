#!/bin/bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
export RELEASE_SHA=$(basename "$RELEASE_DIR")
check_env
compose up -d --wait --wait-timeout 120 db redis
compose up -d --wait --wait-timeout 180 --no-deps api worker beat frontend caddy
