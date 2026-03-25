# Groove Work

Система управления задачами для отдела региональных коммуникаций.
**Стек:** Python 3.11 · Flask 3 · PostgreSQL 15 · Docker

---

## Быстрый старт (dev)

```bash
cp .env.example .env
docker compose up -d
docker compose exec web flask init-db
```

Открыть **http://localhost:5001**
Логин: `admin` / Пароль: `admin123`

---

## Продакшн (nginx + gunicorn)

```bash
cp .env.example .env   # заполнить реальными значениями
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec web flask init-db
```

---

## CLI-команды

| Команда | Описание |
|---|---|
| `flask init-db` | Создать таблицы + суперадмин + базовые данные |
| `flask migrate-db` | Добавить новые колонки без потери данных |
| `flask auto-archive` | Архивировать DONE-задачи старше 7 дней |
| `flask archive-old` | Архивировать задачи старше 365 дней |
| `flask fix-sequences` | Сбросить PostgreSQL sequences после импорта |

**Cron (рекомендуется):**
```
0 3 * * 1  docker compose exec web flask auto-archive
```

---

## Роли пользователей

| Роль | Задачи | Чужие задачи | Удаление задач | Аналитика | Управление системой |
|------|--------|--------------|----------------|-----------|---------------------|
| ТВ-экран (`tv`) | ❌ | ❌ | ❌ | Только TV | ❌ |
| Сотрудник (`staff`) | Свои | ❌ | ❌ | Только свои | ❌ |
| Руководитель (`manager`) | Все | ✅ | ✅ | Все | ❌ |
| Администратор (`admin`) | Все | ✅ | ✅ | Все | Пользователи ≤ manager, Списки |
| Супер-Админ (`super_admin`) | Все | ✅ | ✅ | Все | Полный доступ |

---

## Загрузка файлов

- Лимит: **100 МБ** суммарно на запрос
- При превышении — предложение загрузить на Яндекс Диск
- Файлы отдаются Flask-ом с оригинальными именами (не хешами)

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql://tasktime:tasktime@localhost/tasktime` | БД |
| `SECRET_KEY` | `dev-secret-key-change-me` | Flask secret key |
| `UPLOAD_FOLDER` | `/app/uploads` | Папка для файлов |
| `TZ_OFFSET_HOURS` | `3` | Часовой пояс (МСК = 3) |
| `YANDEX_DISK_TOKEN` | — | OAuth-токен Яндекс Диска (будущая интеграция) |
