# TaskTime Stats

## Быстрый старт (локально)

```bash
# 1. Скопировать env
cp .env.example .env

# 2. Запустить контейнеры
docker compose up -d

# 3. Инициализировать БД (один раз)
docker compose exec web flask init-db
```

Открыть http://localhost:5000
Логин: `admin` / Пароль: `admin123`

## Архивация (по крону)
```
0 3 * * * docker compose exec web flask archive-old
```

## Продакшн (nginx + gunicorn)
```bash
cp .env.example .env  # заполнить реальными значениями
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec web flask init-db
```

## Структура ролей
| Роль | Создание задач | Таймер | Просмотр аналитики | Закрыть задачу | Управление пользователями |
|------|---------------|--------|-------------------|----------------|--------------------------|
| Super Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Руководитель | ✅ | ✅ | ✅ | ✅ | ❌ |
| Администратор | ✅ | ✅ | ✅ | ❌ | ❌ |
| Сотрудник | ❌ | ✅ | ✅ | ❌ | ❌ |
| Заказчик | Внешняя форма | ❌ | ❌ | ❌ | ❌ |
