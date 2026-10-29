#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
test "$(id -u)" = 0 || { echo 'Run with sudo.' >&2; exit 1; }
if systemctl is-active --quiet outsourcing-poll.timer || systemctl is-active --quiet outsourcing-poll.service; then
  echo 'Disable the polling timer and wait for any running deployment to finish first.' >&2
  exit 1
fi
# Install trusted entry points only; no builds, package installs or token changes.
install -d -o root -g root -m 755 /opt/outsourcing-deploy
install -o root -g root -m 755 poller.py /opt/outsourcing-deploy/poller.py
install -o root -g root -m 755 deploy-sha.sh /usr/local/sbin/outsourcing-deploy-sha
echo 'Runner entry point installed. Configure the limited sudoers rule separately.'
