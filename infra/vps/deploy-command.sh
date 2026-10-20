#!/bin/bash
# Forced SSH command for the GitHub Actions account. No interactive shell.
set -euo pipefail
pattern='^deploy ([a-f0-9]{40})$'
if [[ ${SSH_ORIGINAL_COMMAND:-} =~ $pattern ]]; then
    exec sudo -n -- /usr/local/sbin/words-v-deploy "${BASH_REMATCH[1]}"
fi
echo 'Only deploy followed by a full commit SHA is permitted.' >&2
exit 64
