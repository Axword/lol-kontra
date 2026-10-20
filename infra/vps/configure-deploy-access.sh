#!/bin/bash
# Run as root after approving persistent GitHub Actions deployment access.
set -euo pipefail
umask 077
[[ $(id -u) == 0 && $# == 1 && -f "$1" ]] || {
    echo 'Usage: sudo configure-deploy-access.sh PUBLIC_KEY_FILE' >&2; exit 1;
}
public_key=$(cat -- "$1")
[[ "$public_key" =~ ^ssh-ed25519\ [A-Za-z0-9+/=]+(\ [A-Za-z0-9._@-]+)?$ ]] || {
    echo 'Expected one Ed25519 public key.' >&2; exit 1;
}
ssh-keygen -l -f "$1" >/dev/null
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
account=words-deploy
if ! id "$account" >/dev/null 2>&1; then
    useradd --create-home --home-dir /home/words-deploy --shell /bin/bash "$account"
fi
[[ $(id -Gn "$account") == "$account" && $(getent passwd "$account" | cut -d: -f6) == /home/words-deploy ]] || {
    echo 'Existing deployment account has unexpected groups or home.' >&2; exit 1;
}
authorized='restrict,command="/usr/local/sbin/words-v-deploy-command" '"$public_key"
key_file=/home/words-deploy/.ssh/authorized_keys
if [[ -e "$key_file" && $(cat "$key_file") != "$authorized" ]]; then
    echo 'Existing deployment key differs; review its rotation explicitly.' >&2; exit 1;
fi
passwd -l "$account" >/dev/null
chown root:root /home/words-deploy
chmod 0755 /home/words-deploy
install -o root -g root -m 0755 -d /home/words-deploy/.ssh
install -o root -g root -m 0755 "$here/deploy.sh" /usr/local/sbin/words-v-deploy
install -o root -g root -m 0755 "$here/deploy-command.sh" /usr/local/sbin/words-v-deploy-command
rule=$(mktemp)
trap 'rm -f -- "$rule"' EXIT
printf '%s\n' 'words-deploy ALL=(root) NOPASSWD: /usr/local/sbin/words-v-deploy *' > "$rule"
visudo -cf "$rule"
install -o root -g root -m 0440 "$rule" /etc/sudoers.d/words-v-deploy
printf '%s\n' "$authorized" > "$key_file"
chown root:root "$key_file"
chmod 0644 "$key_file"
sshd -t
echo 'Restricted deployment access configured; interactive SSH and forwarding are disabled.'
