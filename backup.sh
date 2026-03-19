#!/usr/bin/env bash
# deploy/backup.sh — создаёт дамп базы данных
# Использование: ./deploy/backup.sh [output_dir]
#
# Требует: docker, запущенный контейнер gw1-db-1
# Дамп сохраняется в <output_dir>/gw1_YYYYMMDD_HHMMSS.sql.gz
set -euo pipefail

OUTPUT_DIR="${1:-./deploy/backups}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILE="$OUTPUT_DIR/gw1_${TIMESTAMP}.sql.gz"

# Читаем переменные из .env если он есть
if [ -f .env ]; then
  # shellcheck source=/dev/null
  set -a; source .env; set +a
fi

DB_NAME="${POSTGRES_DB:-tasktime}"
DB_USER="${POSTGRES_USER:-tasktime}"
CONTAINER="${DB_CONTAINER:-gw1-db-1}"

echo "→ Создаю дамп базы '$DB_NAME' из контейнера '$CONTAINER'..."
docker exec "$CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$FILE"

echo "✓ Дамп сохранён: $FILE ($(du -sh "$FILE" | cut -f1))"
