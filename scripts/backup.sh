#!/usr/bin/env bash
# Postgres 자동 백업 — docker exec pg_dump → backups/cleaning_ops_<TS>.dump.gz
#
# 사용법:
#   bash scripts/backup.sh
# 환경변수 (옵션):
#   CONTAINER=cleanops_postgres
#   DB_USER=cleanops
#   DB_NAME=cleaning_ops
#   OUT_DIR=./backups
#   RETENTION_DAYS=7
#
# cron 예시 (운영 서버, 02:30 KST 매일):
#   30 2 * * *  cd /path/to/design_handoff_cleaning_ops && bash scripts/backup.sh >> logs/backup.log 2>&1

set -euo pipefail

CONTAINER="${CONTAINER:-cleanops_postgres}"
DB_USER="${DB_USER:-cleanops}"
DB_NAME="${DB_NAME:-cleaning_ops}"
OUT_DIR="${OUT_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TS="$(date -u +%Y%m%d_%H%M%SZ)"

mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/cleaning_ops_${TS}.dump.gz"

echo "[backup] dumping $DB_NAME from container $CONTAINER -> $OUT_FILE"
docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc \
  | gzip -9 > "$OUT_FILE"

SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo "[backup] done. size=$SIZE"

echo "[backup] removing files older than ${RETENTION_DAYS} days in $OUT_DIR"
find "$OUT_DIR" -maxdepth 1 -name 'cleaning_ops_*.dump.gz' -mtime "+${RETENTION_DAYS}" -print -delete || true

echo "[backup] current backups:"
ls -la "$OUT_DIR"
