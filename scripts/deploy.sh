#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."

tag="${1:-}"
if [[ ! "$tag" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: bash scripts/deploy.sh <full-40-character-commit-sha>' >&2
  exit 2
fi
# Prevent overlapping manual deployments. Keep previous images for rollback.
exec 9>.deploy.lock
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
test -f backend.env || { echo 'Create backend.env first.' >&2; exit 1; }
export IMAGE_TAG="$tag"
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose up -d --wait --wait-timeout 180
# Recreate Caddy after config changes and resolve current upstream addresses.
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile --force
curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-all-errors http://127.0.0.1/ >/dev/null
curl --fail --silent --show-error --retry 10 --retry-delay 3 --retry-all-errors http://127.0.0.1/api/health \
  | python3 -c 'import json,sys; assert json.load(sys.stdin) == {"status":"ok"}'
# Save the release only after containers and both proxy routes pass.
umask 077
printf 'IMAGE_TAG=%s\n' "$tag" > .env
echo "Deployed $tag"
