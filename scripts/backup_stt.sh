#!/bin/bash
# stt_analysis 스키마 자동 백업
# launchd로 매일 03:00 실행

set -e

BACKUP_DIR="/Users/ez2sarang/Documents/dev/ai/offline-thinking/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/stt_analysis_${DATE}.sql"
KEEP_DAYS=30

# DB 접속 정보 (.env에서 읽기)
ENV_FILE="/Users/ez2sarang/Documents/dev/ai/offline-thinking/api/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | grep -E '^DB_' | xargs)
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-54322}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
DB_NAME="${DB_NAME:-postgres}"

# pg_dump (Docker 컨테이너 경유)
PGPASSWORD="$DB_PASSWORD" docker exec -i supabase_db_dho \
    pg_dump -U "$DB_USER" -d "$DB_NAME" \
    --schema=stt_analysis \
    --no-owner --no-acl \
    > "$FILE"

SIZE=$(du -sh "$FILE" | cut -f1)
echo "[$(date)] 백업 완료: $FILE ($SIZE)"

# 30일 이상 된 백업 자동 삭제
find "$BACKUP_DIR" -name "stt_analysis_*.sql" -mtime +$KEEP_DAYS -delete
echo "[$(date)] ${KEEP_DAYS}일 이상 된 백업 정리 완료"
