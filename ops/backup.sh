#!/usr/bin/env bash
# 상담·견적·결제 기록(SQLite)과 첨부 파일을 매일 백업한다.
# /etc/outsourcing-deploy/backup.env에 BACKUP_S3_URI가 있으면 S3에도 올린다(서버에 IAM 역할 필요).
set -Eeuo pipefail
umask 077
if [[ -f /etc/outsourcing-deploy/backup.env ]]; then source /etc/outsourcing-deploy/backup.env; fi
LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/outsourcing-site}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"

container="$(docker ps -q --filter label=com.docker.compose.project=outsourcing-site --filter label=com.docker.compose.service=backend | head -n1)"
if [[ -z "$container" ]]; then
  container="$(docker ps -q --filter label=com.docker.compose.service=backend | head -n1)"
fi
[[ -n "$container" ]] || { echo "실행 중인 backend 컨테이너를 찾지 못했습니다." >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"; docker exec "$container" rm -f /app/data/.backup.db >/dev/null 2>&1 || true' EXIT

# 첨부 파일 등 데이터 폴더 전체를 복사한 뒤, DB는 실행 중에도 일관된 사본을 만드는 SQLite 백업 API로 바꿔 넣는다.
docker cp "$container:/app/data/." "$work/data"
rm -f "$work/data/site.db" "$work/data/site.db-wal" "$work/data/site.db-shm" "$work/data/.backup.db"
docker exec "$container" python -c "import sqlite3; s = sqlite3.connect('/app/data/site.db'); d = sqlite3.connect('/app/data/.backup.db'); s.backup(d); d.close(); s.close()"
docker cp "$container:/app/data/.backup.db" "$work/data/site.db"

mkdir -p "$LOCAL_DIR"
archive="$LOCAL_DIR/site-$stamp.tar.gz"
tar -czf "$archive" -C "$work" data
find "$LOCAL_DIR" -name 'site-*.tar.gz' -mtime +"$KEEP_DAYS" -delete

if [[ -n "${BACKUP_S3_URI:-}" ]]; then
  aws s3 cp "$archive" "${BACKUP_S3_URI%/}/$(basename "$archive")" --only-show-errors
  echo "S3 업로드 완료: ${BACKUP_S3_URI%/}/$(basename "$archive")"
fi
echo "백업 완료: $archive ($(du -h "$archive" | cut -f1))"
