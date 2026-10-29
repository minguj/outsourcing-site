#!/usr/bin/env bash
set -Eeuo pipefail
# Root-owned, fixed-path sudo entry point. Never execute runner workspace code.
if [[ "$(id -u)" != 0 || "$#" != 1 || ! "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Expected root and exactly one full lowercase commit SHA.' >&2
  exit 2
fi
if /usr/bin/systemctl is-active --quiet outsourcing-poll.timer; then
  echo 'Disable outsourcing-poll.timer before enabling runner deployments.' >&2
  exit 1
fi
# -I ignores PYTHONPATH and user site packages; do not preserve caller env config.
unset RESTORE_ONLY PYTHONPATH PYTHONHOME
exec /usr/bin/python3 -I /opt/outsourcing-deploy/poller.py --sha "$1"
