#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
test "$(id -u)" = 0 || { echo 'sudo 권한이 필요합니다.' >&2; exit 1; }
install -d -m 700 /etc/outsourcing-deploy /var/lib/outsourcing-deploy
install -d -m 755 /opt/outsourcing-deploy
install -m 755 poller.py credentials.py /opt/outsourcing-deploy/
if [[ ! -f /etc/outsourcing-deploy/backend.env ]]; then
  install -m 600 /dev/null /etc/outsourcing-deploy/backend.env
fi
install -m 644 outsourcing-poll.service outsourcing-poll.timer outsourcing-restore.service /etc/systemd/system/
python3 -m py_compile /opt/outsourcing-deploy/poller.py
systemd-analyze verify /etc/systemd/system/outsourcing-poll.service /etc/systemd/system/outsourcing-poll.timer /etc/systemd/system/outsourcing-restore.service
systemctl daemon-reload
systemctl enable outsourcing-restore.service
systemctl enable --now outsourcing-poll.timer
echo '조회 타이머 활성화 완료. 토큰이 없으면 배포하지 않습니다.'
