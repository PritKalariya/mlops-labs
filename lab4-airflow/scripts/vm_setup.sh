#!/usr/bin/env bash
# Install Docker Engine and the Compose plugin from Docker's apt repo on Ubuntu, and add the
# current user to the docker group. Run it on the VM:  bash vm_setup.sh
# After it finishes, open a new SSH session so the docker group applies.
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo "Run as a normal user with sudo, not as root." >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y ca-certificates curl

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker "$USER"

sudo docker --version
sudo docker compose version
echo "Done. Open a new SSH session so '$USER' can run docker without sudo."
