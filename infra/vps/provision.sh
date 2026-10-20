#!/bin/bash
# Run once on a fresh Ubuntu 24.04 VPS after reviewing this file.
set -euo pipefail
umask 077
[[ $(id -u) == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'This provisioner targets Ubuntu 24.04 LTS.' >&2; exit 1; }
if [[ -n "${SSH_CONNECTION:-}" && "${SSH_CONNECTION##* }" != 22 ]]; then
    echo 'This setup opens SSH port 22. Review custom SSH ports before continuing.' >&2; exit 1
fi
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
apt-get install -y ca-certificates curl git python3 ufw restic unattended-upgrades
if ! command -v docker >/dev/null; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: noble\nComponents: stable\nArchitectures: %s\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/docker.sources
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version >/dev/null
systemctl enable --now docker
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
install -d -m 0755 /opt/words-v /opt/words-v/releases
install -d -m 0700 /etc/words-v /var/backups/words-v
if [[ ! -d /opt/words-v/repository.git ]]; then
    git clone --bare https://github.com/Axword/lol-kontra.git /opt/words-v/repository.git
fi
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
install -m 0755 "$here/deploy.sh" /usr/local/sbin/words-v-deploy
install -m 0644 "$here/words-v.service" "$here/words-v-backup.service" "$here/words-v-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable words-v.service
systemctl enable --now words-v-backup.timer
echo 'Host prepared. Configure app.env, SSH keys and off-server backups before the first deployment.'
