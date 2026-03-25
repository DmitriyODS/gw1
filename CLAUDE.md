# Groove Work — CLAUDE.md

Система управления задачами для отдела региональных коммуникаций. Flask + PostgreSQL, деплой через Docker.

---

## Структура проекта

```
gw1/
├── app/
│   ├── blueprints/
│   │   ├── admin_bp.py      — управление пользователями и отделами
│   │   ├── analytics.py     — дашборд, учёт времени, TV-режим
│   │   ├── auth.py          — логин / логаут
│   │   ├── media_plan.py    — медиаплан
│   │   ├── plans.py         — планы задач (конвертируются в задачи)
│   │   ├── profile.py       — профиль, аватар, API статистики по типам
│   │   ├── public.py        — внешняя форма заявок (без авторизации)
│   │   ├── rhythms.py       — повторяющиеся задачи (ритмы)
│   │   └── tasks.py         — основной CRUD задач, таймер, канбан
│   ├── templates/
│   │   ├── base.html        — основной layout, сайдбар, topbar
│   │   ├── analytics/
│   │   │   ├── dashboard.html
│   │   │   ├── time.html    — учёт времени по сотрудникам
│   │   │   └── tv.html      — TV-режим (5 слайдов)
│   │   ├── tasks/
│   │   │   ├── list.html    — канбан-доска
│   │   │   ├── detail.html  — карточка задачи
│   │   │   ├── form.html    — создание/редактирование
│   │   │   └── _card.html   — фрагмент карточки для канбана
│   │   ├── profile.html
│   │   └── public/submit.html — внешняя форма заявок
│   ├── models.py            — все SQLAlchemy-модели
│   ├── factory.py           — create_app(), CLI-команды
│   ├── config.py            — Config из env-переменных
│   ├── extensions.py        — db, login_manager, csrf
│   └── requirements.txt
├── docker-compose.yml       — dev (flask run --debug, порт 5001)
├── docker-compose.prod.yml  — prod (gunicorn 4 workers, nginx, порт 80)
└── CLAUDE.md
```

---

## Запуск (dev)

```bash
docker compose up -d
docker compose exec web flask init-db   # первый запуск: создаёт таблицы + суперадмин
docker compose exec web flask migrate-db  # добавить новые колонки без потери данных
```

**Дефолтные credentials:** `admin` / `admin123`

Dev-сервер: `http://localhost:5001`

---

## Запуск (prod)

```bash
# Создать .env с переменными:
# POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, SECRET_KEY
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec web flask init-db
```

---

## CLI-команды (`flask <команда>`)

| Команда | Что делает |
|---|---|
| `init-db` | Создать все таблицы + суперадмин admin/admin123 + базовые отделы |
| `migrate-db` | Добавить новые колонки в существующие таблицы (безопасно) |
| `auto-archive` | Архивировать DONE-задачи старше 7 дней (запускать еженедельно через cron) |
| `migrate-review` | Перевести все задачи со статусом review → done |
| `fix-none-fields` | Очистить строку "None" в полях customer_* |
| `archive-old` | Архивировать выполненные задачи старше 365 дней |
| `fix-sequences` | Сбросить PostgreSQL-последовательности после ручного импорта данных |

**Cron для авто-архивации** (добавить в crontab на хосте или через docker exec):
```
0 3 * * 1  docker compose exec web flask auto-archive
```

---

## Модели (models.py)

### Task — основная модель задачи
Ключевые поля: `title`, `task_type`, `status`, `urgency`, `deadline`, `assigned_to_id`, `created_by_id`, `department_id`, `tags` (JSON), `dynamic_fields` (JSON), `completed_at`, `updated_at`, `is_archived`

### Роли пользователей (Role)
- `super_admin` — полный доступ
- `manager` — управление + аналитика
- `admin` — управление задачами и пользователями
- `staff` — сотрудник (стандартный доступ)
- `tv` — только TV-режим

### Статусы задач (TaskStatus)
`new` → `in_progress` → `paused` / `done`

Переход в `in_progress` только через кнопку таймера (не drag-and-drop).

### Срочность (Urgency)
`slow` < `normal` < `important` < `urgent`

---

## Типы задач (TASK_TYPES в public.py)

Все 23 типа (slug → метка):
`pub_images`, `banner`, `poster`, `presentation`, `presentation_update`, `text_writing`, `handout`, `placement`, `internal`, `external`, `water_plants`, `exports`, `surveys`, `photo_edit`, `video_edit`, `video_shoot`, `photo_shoot`, `meeting`, `mail_work`, `cloud_work`, `stand_design`, `pub_design`, `branded`

Метки хранятся в `TYPE_LABELS` в `analytics.py`. При добавлении нового типа — обновить оба места.

---

## Ключевые API-эндпоинты

| URL | Описание |
|---|---|
| `GET /tasks` | Канбан-доска (параметр `?sort_new=1` — сортировка «Новых» по активности) |
| `POST /tasks/<id>/timer/start` | Запустить таймер (переводит задачу в in_progress) |
| `POST /tasks/<id>/timer/pause` | Поставить таймер на паузу |
| `POST /tasks/<id>/move` | Переместить задачу (drag-and-drop, кроме in_progress) |
| `POST /tasks/<id>/done` | Закрыть задачу |
| `GET /analytics/tv/data` | JSON для TV-слайдов |
| `GET /analytics/time` | Учёт времени (`?mode=day\|week\|month&offset=0`) |
| `GET /analytics/time/user-detail` | JSON деталей сотрудника для модалки |
| `GET /api/profile/stats` | JSON статистики по типам для профиля (`?mode=day\|week\|month&offset=0`) |
| `GET /submit` | Внешняя форма заявок (без авторизации) |

---

## Архитектурные решения

### Таймер и владение задачей
- Задача имеет `assigned_to_id` — тот, кто сейчас работает
- Таймер запускает только один человек одновременно
- При старте таймера: задача → `in_progress`, пользователь становится `assigned_to`
- При паузе: задача → `paused`, но `assigned_to_id` остаётся
- При закрытии (`done`): `assigned_to_id` = None

### updated_at
Обновляется в `tasks.py` через функцию `touch(task)` при каждом изменении задачи (старт/пауза/делегирование/редактирование/закрытие/drag-and-drop). Используется для сортировки колонок «В работе», «Пауза», «Готово» — свежее изменение всплывает наверх.

### Авто-архивация
- При каждом открытии `/tasks` запускается `_maybe_auto_archive()` (дебаунс 1 час)
- Архивирует DONE-задачи с `completed_at` старше 7 дней

### Временная зона
Все datetime в БД хранятся в **UTC**. Конвертация в локальное время через `TZ_OFFSET_HOURS` (по умолчанию 3, т.е. МСК). Фильтры в `factory.py`: `timeformat`, `shorttime`, `localdate`, `hhmm`. Аналитика и профиль используют `_period_bounds()` для правильных границ периодов.

### TV-режим (5 слайдов)
1. Сегодня — статусы задач + типы + время
2. Сегодня — отделы (donut) + рейтинг сотрудников
3. Текущая неделя — статусы + типы + время
4. Текущая неделя — отделы + рейтинг
5. Всё время — общая статистика

Рейтинг сотрудников: `R = 0.5*(N/N_max) + 0.5*(T/T_max) * 100` где N — закрытые задачи, T — среднее время на задачу. Данные обновляются каждые 30 секунд.

### Внешняя форма заявок
`/submit` — без авторизации. После отправки редирект с `prefill_name/phone/email/dept` в query params — форма предзаполняется для следующей заявки от того же заказчика.

---

## Стек и зависимости

- **Python 3.11**, Flask 3.0.3
- **PostgreSQL 15** (через psycopg2-binary)
- **Flask-SQLAlchemy**, Flask-Login, Flask-WTF (CSRF)
- **Gunicorn** (prod), встроенный Flask dev-сервер (dev)
- **Frontend**: DaisyUI v5 + Tailwind (CDN), Bootstrap Icons (CDN), Chart.js 4.4, Google Material Icons Round (CDN)
- Никаких сборщиков (webpack/vite) — всё через CDN

---

## UI-правила

- **Нет эмодзи** — используем Bootstrap Icons (`bi-*`) или Material Icons Round (`<span class="material-icons-round">`)
- Тема: светлая по умолчанию, переключается через `localStorage('tt-theme')`
- Версия отображается в сайдбаре (`base.html`, строка с `v0.3`)

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql://tasktime:tasktime@localhost/tasktime` | Строка подключения к БД |
| `SECRET_KEY` | `dev-secret-key-change-me` | Flask secret key |
| `UPLOAD_FOLDER` | `/app/uploads` | Путь для загруженных файлов |
| `TZ_OFFSET_HOURS` | `3` | Смещение от UTC (МСК = 3) |
