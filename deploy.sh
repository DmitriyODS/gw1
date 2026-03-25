#!/bin/bash
set -e

COMPOSE="docker compose -f docker-compose.yml"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[deploy]${NC} $1"; }
err() { echo -e "${RED}[deploy]${NC} $1" >&2; exit 1; }

# Проверяем, что запускаем из корня репозитория
[ -f docker-compose.yml ] || err "Запускать из корня репозитория"

log "Останавливаем контейнеры..."
$COMPOSE down

log "Получаем изменения из git..."
git pull || err "git pull завершился с ошибкой"

log "Собираем и запускаем контейнеры..."
$COMPOSE up --build -d

log "Ждём запуска БД..."
sleep 5

log "Запускаем миграцию..."
$COMPOSE exec web flask migrate-db

log "Деплой завершён успешно."
