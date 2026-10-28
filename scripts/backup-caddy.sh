#!/usr/bin/env bash
set -Eeuo pipefail
# Run BEFORE uploading/replacing compose.yaml or Caddyfile on EC2.
cd "${1:-$HOME/outsourcing-site}"
service="${2:-caddy}"
umask 077
backup_dir="$HOME/outsourcing-site-backups/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$backup_dir"
cp -p compose.yaml "$backup_dir/compose.yaml"
for file in compose.override.yaml compose.yml compose.override.yml Caddyfile; do
  if [[ -f "$file" ]]; then cp -p "$file" "$backup_dir/$file"; fi
done
container="$(docker compose ps -q "$service")"
if [[ -z "$container" ]]; then
  echo "Running $service service not found. Inspect existing project/service before replacement." >&2
  exit 1
fi
# Copy the actual running config even when its host path differs.
docker cp "$container:/etc/caddy/Caddyfile" "$backup_dir/Caddyfile.running"
docker inspect --format '{{json .Mounts}}' "$container" > "$backup_dir/caddy-mounts.json"
docker compose config > "$backup_dir/compose.resolved.yaml"
docker compose ps > "$backup_dir/containers.txt"
chmod -R go-rwx "$backup_dir"
echo "Caddy backup completed: $backup_dir"
exit 0
