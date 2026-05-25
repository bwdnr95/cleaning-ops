#!/usr/bin/env bash
# Postgres 복구 — gz dump 파일 -> docker exec pg_restore (DROP + CREATE)
#
# 사용법:
#   bash scripts/restore.sh backups/cleaning_ops_20260524_173000Z.dump.gz
#
# 환경변수 (옵션):
#   CONTAINER=cleanops_postgres
#   DB_USER=cleanops
#   DB_NAME=cleaning_ops

set -euo pipefail

CONTAINER="${CONTAINER:-cleanops_postgres}"
DB_USER="${DB_USER:-cleanops}"
DB_NAME="${DB_NAME:-cleaning_ops}"
SRC="${1:-}"

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
  echo "Usage: $0 <backup-file.dump.gz>" >&2
  echo "  e.g.: $0 backups/cleaning_ops_20260524_173000Z.dump.gz" >&2
  exit 1
fi

cat <<EOF
[restore] WARNING
  - container : $CONTAINER
  - user      : $DB_USER
  - database  : $DB_NAME (will be DROPPED and recreated)
  - source    : $SRC

Continue? [y/N]
EOF
read -r ans
case "$ans" in
  y|Y) ;;
  *)   echo "aborted."; exit 1;;
esac

echo "[restore] backend가 떠 있다면 먼저 종료한 뒤 진행하세요. 5초 후 시작..."
sleep 5

echo "[restore] dropping and recreating $DB_NAME"
docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE);"
docker exec "$CONTAINER" psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $DB_NAME;"

echo "[restore] piping $SRC into pg_restore"
gunzip -c "$SRC" | docker exec -i "$CONTAINER" pg_restore -U "$DB_USER" -d "$DB_NAME" --no-owner --no-privileges

echo "[restore] tables:"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "\dt"

echo "[restore] alembic version:"
docker exec "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT version_num FROM alembic_version;"

echo "[restore] done. backend를 다시 띄우세요."
