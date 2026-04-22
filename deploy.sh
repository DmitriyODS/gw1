#!/bin/bash
set -e

COMPOSE="docker compose -f docker-compose.prod.yml"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $1"; }
err() { echo -e "${RED}[deploy]${NC} $1" >&2; exit 1; }

[ -f docker-compose.prod.yml ] || err "Запускать из корня репозитория (~/gw1)"
[ -f .env ] || err ".env не найден — создайте файл с POSTGRES_*, SECRET_KEY"

log "Получаем изменения из git..."
git pull || err "git pull завершился с ошибкой"

log "Пересобираем образы и перезапускаем контейнеры..."
$COMPOSE up --build -d

log "Ждём готовности БД..."
for i in $(seq 1 30); do
  $COMPOSE exec -T db pg_isready -q && break
  sleep 2
  [ "$i" -eq 30 ] && err "БД не поднялась за 60 секунд"
done

log "Применяем миграции..."
$COMPOSE exec -T web flask --app factory:create_app migrate-db

log "Деплой завершён успешно."
