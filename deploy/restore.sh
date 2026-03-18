#!/usr/bin/env bash
# deploy/restore.sh — восстанавливает базу из дампа
# Использование: ./deploy/restore.sh <path/to/backup.sql.gz>
#
# ВНИМАНИЕ: удаляет все существующие данные в базе!
set -euo pipefail

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
  echo "Использование: $0 <backup.sql.gz>" >&2
  exit 1
fi
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Файл не найден: $BACKUP_FILE" >&2
  exit 1
fi

# Читаем переменные из .env если он есть
if [ -f .env ]; then
  set -a; source .env; set +a
fi

DB_NAME="${POSTGRES_DB:-tasktime}"
DB_USER="${POSTGRES_USER:-tasktime}"
CONTAINER="${DB_CONTAINER:-gw1-db-1}"

echo "→ Восстановление базы '$DB_NAME' из: $BACKUP_FILE"
echo "  ВНИМАНИЕ: существующие данные будут удалены. Продолжить? [y/N]"
read -r CONFIRM
[ "$CONFIRM" = "y" ] || { echo "Отменено."; exit 0; }

echo "→ Пересоздаю базу..."
docker exec "$CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec "$CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

echo "→ Восстанавливаю дамп..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"

echo "✓ База восстановлена из: $BACKUP_FILE"
