#!/bin/sh
# Installs Docker Engine inside an Ubuntu WSL2 distribution (no Docker Desktop needed).
# Run as root inside the distribution:
#   wsl -d Ubuntu -u root -- sh /mnt/<drive>/<path-to-repo>/scripts/install_docker_wsl.sh
# then restart WSL from Windows with `wsl --shutdown`.
set -eu
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq ca-certificates curl >/dev/null
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null

# systemd starts the Docker daemon when the distribution boots
grep -q "systemd=true" /etc/wsl.conf 2>/dev/null || printf '[boot]\nsystemd=true\n' >> /etc/wsl.conf
docker --version
