# Groove Work — CLAUDE.md

Система управления задачами для отдела региональных коммуникаций. Flask + PostgreSQL, деплой через Docker.

---

## Структура проекта

```
gw1/
├── app/
│   ├── blueprints/
│   │   ├── admin_bp.py      — управление пользователями и отделами (только admin+)
│   │   ├── analytics.py     — дашборд, учёт времени, TV-режим, экспорт PDF/Excel
│   │   ├── auth.py          — логин / логаут
│   │   ├── lists_bp.py      — CRUD для TaskType и Department (только admin+)
│   │   ├── media_plan.py    — медиаплан
│   │   ├── plans.py         — планы задач (конвертируются в задачи)
│   │   ├── profile.py       — профиль, аватар, API статистики по типам
│   │   ├── public.py        — внешняя форма заявок (без авторизации) + API task-types
│   │   ├── rhythms.py       — повторяющиеся задачи (ритмы)
│   │   └── tasks.py         — основной CRUD задач, таймер, канбан, скачивание файлов
│   ├── services/
│   │   └── yandex_disk.py   — заготовка интеграции с Яндекс Диском (не активна)
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
│   │   ├── admin/
│   │   │   ├── users.html
│   │   │   └── user_form.html
│   │   ├── profile.html
│   │   └── public/submit.html — внешняя форма заявок
│   ├── models.py            — все SQLAlchemy-модели
│   ├── factory.py           — create_app(), CLI-команды
│   ├── config.py            — Config из env-переменных
│   ├── extensions.py        — db, login_manager, csrf
│   ├── decorators.py        — manager_required, admin_required, super_admin_required
│   └── requirements.txt
├── nginx/nginx.conf         — только reverse proxy, файлы отдаёт Flask (для auth + правильных имён)
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
| `init-db` | Создать все таблицы + суперадмин admin/admin123 + базовые отделы + типы задач |
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

### TaskType — типы задач (таблица в БД)
Поля: `slug`, `label`, `sort_order`. Управляются через раздел «Списки» (`/lists`). При создании нового типа он автоматически появляется во всех формах — задач, планов, ритмов, внешней форме.

### Роли пользователей (Role)
| Роль | Задачи | Чужие задачи | Удаление | Аналитика | Пользователи/Списки |
|------|--------|--------------|----------|-----------|---------------------|
| `tv` | ❌ | ❌ | ❌ | Только TV | ❌ |
| `staff` | Свои | ❌ | ❌ | Только свои | ❌ |
| `manager` | Все | ✅ | ✅ | Все | ❌ |
| `admin` | Все | ✅ | ✅ | Все | ✅ (до manager) |
| `super_admin` | Все | ✅ | ✅ | Все | ✅ (все роли) |

**Свойства User:**
- `can_admin` — super_admin + manager + admin (управление задачами: удаление, пауза, делегирование)
- `can_manage` — super_admin + admin (системное управление: пользователи, списки, архив)
- `is_super_admin` — только super_admin

**Ограничения при создании пользователей:**
- `admin` может создавать/редактировать пользователей с ролью ≤ `manager`
- `super_admin` может назначать любую роль включая `admin`
- Нельзя деактивировать свой аккаунт

**Валидация:**
- Логин: минимум 4 символа, начинается с латинской буквы, допустимы `[A-Za-z0-9_-]`
- Пароль: минимум 6 символов

### Статусы задач (TaskStatus)
`new` → `in_progress` → `paused` / `done`

Переход в `in_progress` только через кнопку таймера (не drag-and-drop).

### Срочность (Urgency)
`slow` < `normal` < `important` < `urgent`

---

## Типы задач

Хранятся в таблице `task_types` (модель `TaskType`). Управляются через `/lists`. При добавлении нового типа через UI он сразу появляется во всех формах (задачи, планы, ритмы, внешняя форма) — они все используют `/api/task-types` или функцию `_get_task_types()`.

Статические метки для аналитики дублируются в `TYPE_LABELS` в `analytics.py` — при добавлении нового типа рекомендуется обновить этот словарь.

---

## Файлы и вложения

- Файлы хранятся в `/app/uploads/` (Docker volume)
- Имена файлов на диске — UUID-хеши (`uuid4().hex + ext`)
- Оригинальные имена хранятся в БД (`TaskAttachment.original_name`, `CommentAttachment.original_name`)
- При скачивании Flask ищет `original_name` в БД и отдаёт с правильным именем через `download_name`
- Nginx НЕ отдаёт `/uploads/` напрямую — всё через Flask (для авторизации + правильных имён)
- Лимит файлов в комментарии: **100 МБ** (суммарно)
- При превышении лимита — модальное окно с предложением загрузить на Яндекс Диск
- Nginx: `client_max_body_size 110M`

---

## Ключевые API-эндпоинты

| URL | Описание |
|---|---|
| `GET /tasks` | Канбан-доска (параметр `?sort_new=1` — сортировка «Новых» по активности) |
| `POST /tasks/<id>/timer/start` | Запустить таймер (переводит задачу в in_progress) |
| `POST /tasks/<id>/timer/pause` | Поставить таймер на паузу |
| `POST /tasks/<id>/move` | Переместить задачу (drag-and-drop, кроме in_progress) |
| `POST /tasks/<id>/done` | Закрыть задачу |
| `GET /uploads/<filename>` | Скачать файл вложения (с оригинальным именем, требует авторизации) |
| `GET /analytics/tv/data` | JSON для TV-слайдов |
| `GET /analytics/time` | Учёт времени (`?mode=day\|week\|month&offset=0`) |
| `GET /analytics/time/user-detail` | JSON деталей сотрудника для модалки |
| `GET /analytics/export/pdf` | Экспорт задач в PDF (с поддержкой кириллицы через DejaVuSans) |
| `GET /analytics/export/excel` | Экспорт задач в Excel |
| `GET /api/task-types` | JSON списка типов задач из БД (используется в формах) |
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
Все datetime в БД хранятся в **UTC**. Конвертация в локальное время через `TZ_OFFSET_HOURS` (по умолчанию 3, т.е. МСК). Фильтры в `factory.py`: `timeformat`, `shorttime`, `localdate`, `hhmm`.

### TV-режим (5 слайдов)
1. Сегодня — статусы задач + типы + время
2. Сегодня — отделы (donut) + рейтинг сотрудников
3. Текущая неделя — статусы + типы + время
4. Текущая неделя — отделы + рейтинг
5. Всё время — общая статистика

Рейтинг сотрудников: `R = 0.5*(N/N_max) + 0.5*(T/T_max) * 100` где N — закрытые задачи, T — среднее время на задачу. Данные обновляются каждые 30 секунд.

### Внешняя форма заявок
`/submit` — без авторизации. После отправки редирект с `prefill_name/phone/email/dept` в query params — форма предзаполняется для следующей заявки от того же заказчика.

### PDF-экспорт и кириллица
PDF генерируется через `reportlab`. Для поддержки кириллицы используется шрифт DejaVuSans, устанавливаемый через `fonts-dejavu-core` в Dockerfile. Функция `_register_cyrillic_font()` в `analytics.py` ищет шрифт по нескольким системным путям с fallback.

### Яндекс Диск (заготовка)
`app/services/yandex_disk.py` — заготовка для загрузки файлов задач на Яндекс Диск. Не активна. Требует: регистрации приложения на oauth.yandex.ru, переменной окружения `YANDEX_DISK_TOKEN`, установки `pip install yadisk`.

---

## Стек и зависимости

- **Python 3.11**, Flask 3.0.3
- **PostgreSQL 15** (через psycopg2-binary)
- **Flask-SQLAlchemy**, Flask-Login, Flask-WTF (CSRF)
- **Gunicorn** (prod), встроенный Flask dev-сервер (dev)
- **openpyxl** — экспорт в Excel
- **reportlab** — экспорт в PDF (с DejaVuSans для кириллицы)
- **Frontend**: DaisyUI v5 + Tailwind (CDN), Bootstrap Icons (CDN), Chart.js 4.4, Google Material Icons Round (CDN)
- Никаких сборщиков (webpack/vite) — всё через CDN

---

## UI-правила

- **Нет эмодзи** — используем Bootstrap Icons (`bi-*`) или Material Icons Round (`<span class="material-icons-round">`)
- Тема: светлая по умолчанию, переключается через `localStorage('tt-theme')`
- Версия отображается в сайдбаре (`base.html`, строка с `v0.3`)
- «По типам» на дашборде — горизонтальный bar chart (не doughnut), высота динамическая

---

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `postgresql://tasktime:tasktime@localhost/tasktime` | Строка подключения к БД |
| `SECRET_KEY` | `dev-secret-key-change-me` | Flask secret key |
| `UPLOAD_FOLDER` | `/app/uploads` | Путь для загруженных файлов |
| `TZ_OFFSET_HOURS` | `3` | Смещение от UTC (МСК = 3) |
| `YANDEX_DISK_TOKEN` | — | OAuth-токен Яндекс Диска (для будущей интеграции) |
