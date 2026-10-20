#!/bin/bash
# Keep the existing SSH connection open; first test key login in a second session.
set -euo pipefail
[[ $(id -u) == 0 && ${2:-} == --key-login-confirmed ]] || {
    echo 'Usage: sudo bash harden-ssh.sh USER --key-login-confirmed' >&2; exit 1;
}
account=${1:-}
[[ "$account" =~ ^[a-z_][a-z0-9_-]*$ && "$account" != root ]] || { echo 'Use a non-root SSH account.' >&2; exit 1; }
account_home=$(getent passwd "$account" | cut -d: -f6)
[[ -n "$account_home" && -s "$account_home/.ssh/authorized_keys" ]] || { echo 'Configure and test the account key first.' >&2; exit 1; }
target=/etc/ssh/sshd_config.d/00-words-v.conf
[[ ! -e "$target" ]] || { echo 'SSH hardening file already exists; review it instead of overwriting.' >&2; exit 1; }
printf 'PubkeyAuthentication yes\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\n' > "$target"
if ! /usr/sbin/sshd -t; then
    rm -- "$target"
    echo 'SSH configuration validation failed; new snippet removed.' >&2; exit 1
fi
systemctl reload ssh.service
echo 'SSH key authentication enforced. Test another connection before closing this one.'
