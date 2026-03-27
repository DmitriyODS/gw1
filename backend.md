# Backend API — Спецификация для Go + Fiber

> Полное описание backend-части Groove Work для переписывания с Python/Flask на Go/Fiber.
> БД: PostgreSQL 15, без ORM — чистый SQL (pgx или sqlx).
> Аутентификация: JWT (access + refresh tokens) вместо сессий.

---

## 1. Схема базы данных

### 1.1 users

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | SERIAL | PK | |
| username | VARCHAR(80) | UNIQUE, NOT NULL | Логин: `^[A-Za-z][A-Za-z0-9_\-]{3,}$` |
| email | VARCHAR(120) | UNIQUE, NOT NULL | |
| password_hash | VARCHAR(256) | NOT NULL | bcrypt hash |
| full_name | VARCHAR(200) | NOT NULL | |
| role | VARCHAR(20) | NOT NULL, DEFAULT 'staff' | Одно из: `super_admin`, `admin`, `manager`, `staff`, `tv` |
| is_active | BOOLEAN | DEFAULT TRUE | |
| created_at | TIMESTAMP | DEFAULT NOW() | UTC |
| mail_user | VARCHAR(200) | NULL | Персональный IMAP/SMTP логин |
| mail_password | VARCHAR(200) | NULL | Персональный IMAP/SMTP пароль |

### 1.2 departments

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| name | VARCHAR(200) | UNIQUE, NOT NULL |
| head | VARCHAR(200) | NOT NULL, DEFAULT '' |

### 1.3 task_types

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| slug | VARCHAR(50) | UNIQUE, NOT NULL |
| label | VARCHAR(200) | NOT NULL |
| sort_order | INTEGER | DEFAULT 0 |

### 1.4 tasks

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | SERIAL | PK | |
| title | VARCHAR(500) | NOT NULL | |
| description | TEXT | | |
| customer_name | VARCHAR(200) | | Заказчик ФИО |
| customer_phone | VARCHAR(50) | | |
| customer_email | VARCHAR(200) | | |
| department_id | INTEGER | FK → departments.id | |
| task_type | VARCHAR(50) | | slug из task_types |
| urgency | VARCHAR(20) | DEFAULT 'normal' | slow / normal / important / urgent |
| status | VARCHAR(20) | DEFAULT 'new' | new / in_progress / paused / done |
| deadline | TIMESTAMP | | UTC |
| created_by_id | INTEGER | FK → users.id, NULL | NULL для внешних заявок |
| assigned_to_id | INTEGER | FK → users.id, NULL | Кто сейчас работает |
| parent_task_id | INTEGER | FK → tasks.id, NULL | Для подзадач |
| tags | JSONB | DEFAULT '[]' | Массив строк: дизайн, текст, публикация, фото/видео, внутреннее, внешнее |
| dynamic_fields | JSONB | DEFAULT '{}' | Произвольные поля: clarification, event_date, pub_date, platforms, subtype, pub_url, revision_ref |
| is_archived | BOOLEAN | DEFAULT FALSE | |
| is_external | BOOLEAN | DEFAULT FALSE | Создана через внешнюю форму /submit |
| archived_at | TIMESTAMP | | |
| completed_at | TIMESTAMP | | |
| created_at | TIMESTAMP | DEFAULT NOW() | UTC |
| updated_at | TIMESTAMP | DEFAULT NOW() | Обновляется при любом изменении задачи |

**Индексы:**
```sql
CREATE INDEX ix_tasks_status ON tasks (status);
CREATE INDEX ix_tasks_archived ON tasks (is_archived);
CREATE INDEX ix_tasks_urgency ON tasks (urgency);
CREATE INDEX ix_tasks_deadline ON tasks (deadline);
CREATE INDEX ix_tasks_assigned_to ON tasks (assigned_to_id);
CREATE INDEX ix_tasks_department ON tasks (department_id);
CREATE INDEX ix_tasks_created_by ON tasks (created_by_id);
CREATE INDEX ix_tasks_completed_at ON tasks (completed_at);
CREATE INDEX ix_tasks_created_at ON tasks (created_at);
```

### 1.5 task_attachments

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| task_id | INTEGER | FK → tasks.id, NOT NULL |
| filename | VARCHAR(255) | UUID-имя на диске (может быть NULL если только на YDisk) |
| original_name | VARCHAR(255) | Оригинальное имя файла |
| uploaded_at | TIMESTAMP | DEFAULT NOW() |
| yadisk_path | VARCHAR(1000) | NULL |
| yadisk_url | VARCHAR(1000) | NULL, публичная ссылка |
| yadisk_folder_url | VARCHAR(1000) | NULL |

### 1.6 task_comments

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| task_id | INTEGER | FK → tasks.id, NOT NULL |
| user_id | INTEGER | FK → users.id, NOT NULL |
| text | TEXT | |
| filename | VARCHAR(255) | Legacy single-file |
| original_name | VARCHAR(255) | Legacy single-file |
| created_at | TIMESTAMP | DEFAULT NOW() |

### 1.7 comment_attachments

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| comment_id | INTEGER | FK → task_comments.id, NOT NULL, ON DELETE CASCADE |
| filename | VARCHAR(255) | |
| original_name | VARCHAR(255) | |
| uploaded_at | TIMESTAMP | DEFAULT NOW() |
| yadisk_path | VARCHAR(1000) | NULL |
| yadisk_url | VARCHAR(1000) | NULL |
| yadisk_folder_url | VARCHAR(1000) | NULL |

### 1.8 time_logs

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| task_id | INTEGER | FK → tasks.id, NOT NULL |
| user_id | INTEGER | FK → users.id, NOT NULL |
| started_at | TIMESTAMP | NOT NULL, DEFAULT NOW() |
| ended_at | TIMESTAMP | NULL (NULL = таймер запущен) |

**Индексы:**
```sql
CREATE INDEX ix_timelogs_user_ended ON time_logs (user_id, ended_at);
CREATE INDEX ix_timelogs_task ON time_logs (task_id);
CREATE INDEX ix_timelogs_started_at ON time_logs (started_at);
```

### 1.9 rhythms

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | SERIAL | PK | |
| name | VARCHAR(200) | NOT NULL | Название ритма |
| description | TEXT | | |
| frequency | VARCHAR(20) | NOT NULL, DEFAULT 'daily' | daily / weekly / monthly |
| day_of_week | INTEGER | NULL | 0-6 (Пн-Вс) для weekly |
| day_of_month | INTEGER | NULL | 1-31 для monthly |
| trigger_time | VARCHAR(5) | NULL | "HH:MM", напр. "09:00" |
| task_title | VARCHAR(500) | NOT NULL | Заголовок создаваемой задачи |
| task_description | TEXT | | |
| task_tags | JSONB | DEFAULT '[]' | |
| task_urgency | VARCHAR(20) | DEFAULT 'normal' | |
| task_type | VARCHAR(50) | | |
| department_id | INTEGER | FK → departments.id, NULL | |
| is_active | BOOLEAN | DEFAULT TRUE | |
| last_run_at | TIMESTAMP | NULL | |
| created_at | TIMESTAMP | DEFAULT NOW() | |
| created_by_id | INTEGER | FK → users.id, NULL | |

### 1.10 plan_groups

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| name | VARCHAR(200) | NOT NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |
| created_by_id | INTEGER | FK → users.id, NULL |

### 1.11 plans

| Колонка | Тип | Ограничения |
|---------|-----|-------------|
| id | SERIAL | PK |
| title | VARCHAR(500) | NOT NULL |
| description | TEXT | |
| customer_name | VARCHAR(200) | |
| customer_phone | VARCHAR(50) | |
| customer_email | VARCHAR(200) | |
| department_id | INTEGER | FK → departments.id, NULL |
| task_type | VARCHAR(50) | |
| urgency | VARCHAR(20) | DEFAULT 'normal' |
| tags | JSONB | DEFAULT '[]' |
| dynamic_fields | JSONB | DEFAULT '{}' |
| group_id | INTEGER | FK → plan_groups.id, NULL |
| release_date | TIMESTAMP | NULL |
| is_converted | BOOLEAN | DEFAULT FALSE |
| converted_task_id | INTEGER | FK → tasks.id, NULL |
| created_by_id | INTEGER | FK → users.id, NULL |
| created_at | TIMESTAMP | DEFAULT NOW() |

---

## 2. Роли и права доступа

### 2.1 Роли (от наименьших прав к наибольшим)

| Роль | Описание |
|------|----------|
| `tv` | Только просмотр TV-режима аналитики |
| `staff` | Работа со своими задачами, просмотр своей аналитики |
| `manager` | Все задачи, удаление, пауза чужих, делегирование, аналитика всех |
| `admin` | То же + управление пользователями (до manager включительно) и списками |
| `super_admin` | Всё, включая назначение роли admin, импорт/экспорт данных |

### 2.2 Свойства (вычисляемые)

| Свойство | Роли | Описание |
|----------|------|----------|
| `can_admin` | super_admin, admin, manager | Управление задачами: удаление, пауза чужих, делегирование |
| `can_manage` | super_admin, admin | Системное управление: пользователи, списки, архив |
| `is_super_admin` | super_admin | Полный доступ |

### 2.3 Ограничения при создании/редактировании пользователей

- `admin` может создавать/редактировать пользователей с ролями: `manager`, `staff`, `tv`
- `super_admin` может назначать любую роль включая `admin` и `super_admin`
- Нельзя деактивировать свой аккаунт
- Нельзя редактировать super_admin если ты не super_admin
- Нельзя удалить super_admin

### 2.4 Валидация

- **Логин**: минимум 4 символа, начинается с латинской буквы, допустимы `[A-Za-z0-9_-]`
- **Пароль**: минимум 6 символов

---

## 3. Аутентификация

### Текущая реализация (Flask)
Session-based через Flask-Login + cookie.

### Рекомендация для Go + Vue
JWT-based:
- `POST /api/auth/login` → access_token (короткоживущий, 15-30 мин) + refresh_token (httpOnly cookie, 7-30 дней)
- `POST /api/auth/refresh` → новый access_token
- `POST /api/auth/logout` → инвалидация refresh_token
- Все защищённые эндпоинты: `Authorization: Bearer <access_token>`

---

## 4. API-эндпоинты

> Все эндпоинты возвращают JSON. Все datetime в UTC (формат ISO 8601).
> Пагинация: `?page=1&per_page=30`. Фильтры через query params.
> Префикс: `/api/v1/`

### 4.1 Auth

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/auth/login` | public | Логин: `{username, password}` → `{access_token, refresh_token, user}` |
| POST | `/auth/refresh` | public (refresh cookie) | Обновление access_token |
| POST | `/auth/logout` | auth | Выход |

---

### 4.2 Tasks (основной CRUD)

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/tasks` | auth | Список задач для канбан-доски. Query: `?sort_new=1` (сортировка новых по updated_at) |
| GET | `/tasks/:id` | auth | Детали задачи (с логами, комментариями, вложениями, подзадачами) |
| POST | `/tasks` | auth | Создать задачу |
| PUT | `/tasks/:id` | auth | Обновить задачу |
| DELETE | `/tasks/:id` | can_admin | Удалить задачу |

#### 4.2.1 GET `/tasks` — Канбан-доска

**Response:**
```json
{
  "tasks": [
    {
      "id": 1,
      "title": "...",
      "status": "new",
      "urgency": "normal",
      "tags": ["дизайн"],
      "is_external": false,
      "is_overdue": false,
      "deadline": "2025-01-15T10:00:00Z",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-10T12:00:00Z",
      "department": {"id": 1, "name": "IT отдел"},
      "assigned_to": {"id": 2, "full_name": "Иванов И.И."},
      "total_seconds": 3600,
      "active_timers": [
        {"user_id": 2, "user_name": "Иванов И.И.", "started_at": "..."}
      ],
      "my_timer_active": false
    }
  ]
}
```

**Логика сортировки:**
- Колонки `in_progress`, `paused`, `done`: по `updated_at` DESC (свежее наверху)
- Колонка `new` (по умолчанию): просроченные первыми → по urgency DESC → по deadline ASC
- Колонка `new` (если `sort_new=1`): по `updated_at` DESC
- Не показывать `is_archived=true` (исключение: archived done — показывать в колонке done, но визуально маркировать)

**Фильтрация:**
- Задачи делятся в колонке `new` на две секции: «Заявки» (`is_external=true`) и «Задачи» (`is_external=false`)

#### 4.2.2 POST `/tasks` — Создание задачи

**Request (обычная задача):**
```json
{
  "title": "...",
  "description": "...",
  "task_type": "banner",
  "urgency": "normal",
  "deadline": "2025-02-01T10:00:00Z",
  "department_id": 1,
  "tags": ["дизайн"],
  "customer_name": "...",
  "customer_phone": "...",
  "customer_email": "...",
  "dynamic_fields": {"clarification": "..."},
  "parent_task_id": null
}
```
+ multipart для файлов (attachments)

**Валидация:**
- `task_type` обязателен (400 если не указан)
- `title` обязателен

**Request (режим публикации — `create_mode=publication`):**

Создаёт 3 задачи:
1. Родительская: `task_type=placement`, `tags=["публикация"]`
2. Подзадача: `title="Картинки — {title}"`, `task_type=pub_images`, `tags=["дизайн"]`
3. Подзадача: `title="Текст — {title}"`, `task_type=text_writing`, `tags=["текст"]`

dynamic_fields для публикации: `{pub_date, platforms: [...]}`

#### 4.2.3 PUT `/tasks/:id`

Обновляет поля задачи. Обязательно обновляет `updated_at`.

#### 4.2.4 DELETE `/tasks/:id`

Требует `can_admin`. Каскадно:
1. Удалить все `task_attachments` (+ физически файлы + файлы с YDisk)
2. Удалить все `time_logs`
3. Обнулить `parent_task_id` у подзадач
4. Обнулить `converted_task_id` у планов
5. Удалить задачу

---

### 4.3 Timer API

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/tasks/:id/timer/start` | auth | Запустить таймер |
| POST | `/tasks/:id/timer/force-start` | auth | Принудительный старт (остановить текущий таймер) |
| POST | `/tasks/:id/timer/pause` | auth | Остановить таймер |
| GET | `/tasks/my-timer` | auth | Текущий активный таймер пользователя |

#### 4.3.1 POST `/tasks/:id/timer/start`

**Бизнес-логика (критически важная):**

1. Если задача `done` → 400 "Нельзя запустить таймер для завершённой задачи"
2. Если задача `is_external=true` и `task_type=NULL` → 400 `{error: "need_task_type", task_id}`
3. Если `assigned_to_id != NULL` и `assigned_to_id != current_user.id` → ответ `{taken: true, by: "Имя"}`
4. Если уже есть активный time_log для текущего пользователя на **этой** задаче → `{success: true, already_running: true}`
5. Если есть активный time_log для текущего пользователя на **другой** задаче → `{conflict: true, active_task_id, active_task_title}`
6. Иначе:
   - Создать `time_log {task_id, user_id, started_at=NOW()}`
   - Установить `task.status = 'in_progress'`
   - Установить `task.assigned_to_id = current_user.id`
   - Обновить `task.updated_at`

#### 4.3.2 POST `/tasks/:id/timer/force-start`

Тот же flow, но сначала:
1. Найти активный time_log текущего пользователя
2. Установить ему `ended_at = NOW()`
3. Проверить, остались ли активные таймеры у других пользователей на той задаче
4. Если нет → установить предыдущей задаче `status = 'paused'`
5. Затем запустить новый таймер (шаг 6 из start)

**Response:** `{success, started_at, prev_task_status}`

#### 4.3.3 POST `/tasks/:id/timer/pause`

1. Найти активный time_log (task_id, user_id, ended_at=NULL)
2. Установить `ended_at = NOW()`
3. Если у этой задачи не осталось активных таймеров → `task.status = 'paused'`
4. Обновить `task.updated_at`

**Response:** `{success, task_status}`

---

### 4.4 Kanban move / task actions

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/tasks/:id/move` | auth (owner/creator/can_admin) | Drag-and-drop перемещение |
| POST | `/tasks/:id/done` | auth (assigned/can_admin) | Закрыть задачу |
| POST | `/tasks/:id/delegate` | auth (assigned/can_admin) | Делегировать |
| POST | `/tasks/:id/admin-pause` | can_admin | Принудительная пауза |
| POST | `/tasks/:id/unassign` | auth (assigned/can_admin) | Снять назначение |
| POST | `/tasks/:id/unarchive` | can_admin | Разархивировать |
| POST | `/tasks/archive-done` | can_admin | Архивировать все done |

#### 4.4.1 POST `/tasks/:id/move`

**Request:** `{status: "new"|"paused"|"done"}`

**Правила:**
- `in_progress` запрещён через move (только через таймер) → 400
- Если `is_external=true` и `task_type=NULL` → 400 `{error: "need_task_type"}`
- Все активные таймеры на задаче останавливаются
- При move в `new`: `assigned_to_id = NULL`
- При move из `done`: `completed_at = NULL` (предотвращает авто-архивацию)
- Обновить `updated_at`
- **Права:** assigned_to == current_user ИЛИ created_by == current_user ИЛИ can_admin

#### 4.4.2 POST `/tasks/:id/done`

**Правила:**
- Если `is_external=true` и `task_type=NULL` → запрет
- Если есть открытые подзадачи (status != done, is_archived=false) → запрет
- Остановить все активные таймеры
- `status = 'done'`, `completed_at = NOW()`, `assigned_to_id = NULL`
- **Права:** assigned_to == current_user ИЛИ can_admin

#### 4.4.3 POST `/tasks/:id/delegate`

**Request:** `{user_id: 123}`

1. Остановить таймер текущего assigned_to (если есть)
2. Установить `assigned_to_id = new_user_id`
3. Если `status = 'in_progress'` → `status = 'paused'`
4. **Права:** assigned_to == current_user ИЛИ can_admin

#### 4.4.4 POST `/tasks/:id/admin-pause`

1. Остановить все активные таймеры (`ended_at = NOW()`)
2. `status = 'paused'`
3. **Только если** status == 'in_progress'

---

### 4.5 Comments

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/tasks/:id/comments` | auth | Добавить комментарий (text + files) |
| DELETE | `/tasks/:id/comments/:comment_id` | auth (author/can_admin) | Удалить комментарий |

**POST:** multipart form: `text` + `files[]`
- Если ни text ни files не переданы → 400
- Файлы: UUID-имя на диске, original_name в БД
- Яндекс Диск: если настроен — загрузка туда, fallback на локальное хранение

**DELETE:** каскадно удаляет comment_attachments (+ физические файлы + файлы с YDisk)

---

### 4.6 Attachments

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/uploads/:filename` | auth | Скачать файл (с оригинальным именем) |
| GET | `/tasks/:id/download-zip` | auth | Скачать все файлы задачи ZIP-архивом |
| DELETE | `/tasks/:id/attachments/:att_id` | auth | Удалить вложение |

**GET `/uploads/:filename`:**
- Искать original_name: сначала в task_attachments, потом в comment_attachments, потом legacy (task_comments.filename)
- Отдавать файл с `Content-Disposition: attachment; filename="original_name"`

---

### 4.7 Task polling

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/tasks/poll` | auth | Состояния задач для live-обновления канбана |
| GET | `/tasks/:id/card` | auth | HTML/JSON одной карточки (для переотрисовки после изменений) |

**GET `/tasks/poll`** — лёгкий endpoint, возвращает:
```json
{
  "123": {"status": "in_progress", "assigned_to": 5, "archived": false},
  "124": {"status": "done", "assigned_to": null, "archived": true}
}
```

> Рекомендация: в новой архитектуре заменить polling на WebSocket.

---

### 4.8 Public (без аутентификации)

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/public/submit` | public | Создать внешнюю заявку |
| GET | `/api/departments` | public | Список подразделений |
| GET | `/api/task-types` | public | Список типов задач |

#### 4.8.1 POST `/public/submit`

**Request:** multipart form:
```
title, description, customer_name, customer_phone, customer_email,
department_id, card_choice, clarification, attachments[]
```

**Логика:**
- `card_choice` маппится на tags через CARD_CHOICES (см. раздел 8)
- `task_type = NULL` (обязательно — сотрудник заполняет позже)
- `is_external = true`
- `created_by_id = NULL`
- Файлы: загрузка на YDisk (если настроен), fallback — локально

**Response:** redirect или `{success: true, task_id}`

---

### 4.9 Analytics

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/analytics/dashboard` | auth | Статистика: по статусам, типам, отделам, топ сотрудников |
| GET | `/analytics/time` | auth | Учёт времени по сотрудникам |
| GET | `/analytics/time/user-detail` | auth | Детали по сотруднику |
| GET | `/analytics/tv/data` | auth (tv+) | JSON для TV-режима (5 слайдов) |
| GET | `/analytics/export/excel` | auth | Экспорт задач в Excel |
| GET | `/analytics/export/pdf` | auth | Экспорт задач в PDF |
| GET | `/analytics/export/user-stats-excel` | auth | Экспорт статистики сотрудника в Excel |

#### 4.9.1 GET `/analytics/dashboard`

**Query:** `?period=day|week|month|year`

**Response:**
```json
{
  "by_status": {"new": 10, "in_progress": 5, "paused": 3, "done": 20},
  "type_stats": [["Разработка баннера", 8], ...],
  "type_by_status": {
    "Разработка баннера": {"new": 2, "in_progress": 1, "paused": 0, "done": 5}
  },
  "dept_stats": [["IT отдел", 12], ...],
  "dept_by_status": {...},
  "top_customers": [["Иванов", 5], ...],
  "top_dept_incoming": [["IT отдел", 12], ...],
  "top_tasks": [["Сотрудник А", 8], ...],
  "top_time": [["Сотрудник Б", 36000], ...],
  "burnup": {
    "dates": ["01.01", "02.01", ...],
    "created": [1, 3, 5, ...],
    "done": [0, 1, 2, ...]
  }
}
```

**Вычисление периода:**
- `day`: от 00:00 сегодня (локальное время) до сейчас
- `week`: от понедельника 00:00 текущей недели
- `month`: от 1-го числа текущего месяца
- `year`: от 1 января текущего года
- Все границы конвертируются из локального времени (UTC + TZ_OFFSET_HOURS) в UTC

#### 4.9.2 GET `/analytics/time`

**Query:** `?mode=day|week|month&offset=0` (offset: 0=текущий, -1=предыдущий)

**Права:**
- `staff` видит только себя
- `can_admin` видит всех

**Response:** массив сотрудников с:
- `done` — закрытые задачи за период
- `secs` — суммарное время (секунды)
- `score` — рейтинг (0-100)
- `rank` — место в рейтинге

#### 4.9.3 GET `/analytics/time/user-detail`

**Query:** `?user_id=5&mode=week&offset=0`

**Response:**
```json
{
  "user_name": "...",
  "period_label": "24.03 – 30.03.2025",
  "total_tasks": 12,
  "total_secs": 28800,
  "tasks": [
    {"id": 1, "title": "...", "type": "Баннер", "secs": 3600, "completed_at": "28.03 14:30"}
  ],
  "by_type": [{"label": "Баннер", "cnt": 5, "secs": 18000}],
  "by_hour": [0,0,0,0,0,0,0,0,1,3,5,2,...],
  "work_by_hour": [0,0,0,0,0,0,0,0,15,60,45,30,...]
}
```

#### 4.9.4 GET `/analytics/tv/data`

**Response (5 слайдов):**
```json
{
  "today": {
    "status": {"new": 2, "in_progress": 1, "paused": 0, "done": 3},
    "types": [{"label": "Баннер", "cnt": 2}],
    "total_secs": 7200,
    "depts": [{"name": "IT", "cnt": 5}],
    "staff": [{"name": "Иванов", "score": 85, "tasks": 3, "secs": 3600}]
  },
  "week": { ... },
  "alltime": {
    "new": 100, "in_progress": 50, "done": 500,
    "types": [...], "depts": [...], "staff": [...]
  }
}
```

**Формула рейтинга:**
```
R_i = (0.5 * N_i/N_max + 0.5 * T_min/T_i) * 100

N_i = кол-во закрытых задач сотрудника
N_max = максимум среди всех
T_i = среднее время на задачу (сек)
T_min = минимальное среднее время (лучший)
```

Сотрудник с 0 задач не участвует в рейтинге. `alltime.staff` считается за текущий год.

---

### 4.10 Profile

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/profile` | auth | Данные профиля + статистика |
| PUT | `/profile` | auth | Обновить full_name, password |
| POST | `/profile/avatar` | auth | Загрузить аватар (crop 256x256 PNG) |
| DELETE | `/profile/avatar` | auth | Сбросить аватар |
| GET | `/api/avatar/:user_id` | public | Получить аватар (PNG или сгенерированный SVG) |
| GET | `/api/profile/stats` | auth | Статистика по типам |
| POST | `/api/user/settings` | auth | Сохранить mail_user/mail_password |
| POST | `/api/user/mail-clear` | auth | Очистить почтовые настройки |

#### 4.10.1 GET `/api/avatar/:user_id`

Если файл `avatars/{user_id}.png` существует → отдать PNG.
Иначе → сгенерировать детерминистический pixel-art SVG:
- 8x8 сетка, симметричная горизонтально (4 столбца → mirror)
- Цвет: HSL от seed=user_id
- Random(seed=user_id), порог: `random() > 0.42`

#### 4.10.2 GET `/api/profile/stats`

**Query:** `?mode=day|week|month&offset=0`

**Response:**
```json
{
  "label": "24.03 – 30.03.2025",
  "total_tasks": 5,
  "total_secs": 14400,
  "by_type": [{"label": "Баннер", "cnt": 3, "secs": 7200}],
  "score": 72,
  "rank": 3,
  "total_ranked": 8
}
```

---

### 4.11 Admin — Пользователи

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/admin/users` | can_manage | Список пользователей |
| POST | `/admin/users` | can_manage | Создать пользователя |
| PUT | `/admin/users/:id` | can_manage | Обновить |
| DELETE | `/admin/users/:id` | can_manage | Удалить (кроме super_admin) |

---

### 4.12 Lists — Типы задач и Подразделения (CRUD)

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| POST | `/lists/task-types` | can_manage | Создать тип: `{slug, label}` |
| PUT | `/lists/task-types/:id` | can_manage | Обновить: `{label}` |
| DELETE | `/lists/task-types/:id` | can_manage | Удалить |
| GET | `/lists/task-types/export` | can_manage | Экспорт JSON |
| POST | `/lists/task-types/import` | can_manage | Импорт JSON |
| POST | `/lists/departments` | can_manage | Создать: `{name, head}` |
| PUT | `/lists/departments/:id` | can_manage | Обновить: `{name, head}` |
| DELETE | `/lists/departments/:id` | can_manage | Удалить |
| GET | `/lists/departments/export` | can_manage | Экспорт JSON |
| POST | `/lists/departments/import` | can_manage | Импорт JSON |

---

### 4.13 Rhythms — Повторяющиеся задачи

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/rhythms` | auth | Список всех ритмов |
| POST | `/rhythms` | auth | Создать ритм |
| PUT | `/rhythms/:id` | auth | Обновить |
| POST | `/rhythms/:id/toggle` | auth | Вкл/выкл |
| POST | `/rhythms/:id/run` | auth | Принудительно создать задачу |
| DELETE | `/rhythms/:id` | auth | Удалить |

**Создание задачи из ритма:**
- Стандартная задача из полей ритма
- Если `task_type == 'publication'` → создать + 2 подзадачи: `[Дизайн]` и `[Текст]`
- Обновить `rhythm.last_run_at = NOW()`

**Логика `is_due` (для cron/scheduler):**
1. Если `is_active=false` → false
2. Если `last_run_at` сегодня (МСК) → false
3. Проверить день: daily=всегда, weekly=день_недели, monthly=день_месяца
4. Если `trigger_time` задано → true только после этого времени (МСК)

---

### 4.14 Plans — Планы задач

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/plans` | auth | Список неконвертированных планов |
| POST | `/plans` | auth | Создать план |
| PUT | `/plans/:id` | auth | Обновить |
| POST | `/plans/:id/push` | auth | Конвертировать в задачу (создать задачу, удалить план) |
| DELETE | `/plans/:id` | auth (author/can_admin) | Удалить |
| POST | `/plans/groups` | auth | Создать группу |
| DELETE | `/plans/groups/:id` | can_admin | Удалить группу (планы отвязываются, не удаляются) |

**Query для GET:** `?group=<group_id>` — фильтр по группе

**Push to board:**
- Создать Task из Plan (все поля)
- Если `task_type == 'publication'` → + 2 подзадачи
- Удалить план
- **НЕ** помечать is_converted — просто удаляем

---

### 4.15 Media Plan

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/media-plan` | auth | Календарный вид публикаций |
| GET | `/media-plan/export` | auth | Экспорт в Excel |

**Query:** `?month=2025-03`

**Логика:**
- Отбор задач с `task_type IN ('placement', 'publication')`, `is_archived=false`
- Группировка по `dynamic_fields.pub_date` (ISO datetime → дата в месяце)
- Задачи без pub_date → отдельная секция

---

### 4.16 Mail (IMAP/SMTP клиент)

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/mail/list` | auth | Список писем. Query: `?folder=inbox|sent&page=1&refresh=0|1` |
| GET | `/mail/message/:uid` | auth | Тело письма + вложения |
| GET | `/mail/attachment/:uid/:part_index` | auth | Скачать вложение письма |
| POST | `/mail/send` | auth | Отправить письмо: `{to, cc, subject, body, attachments[]}` |
| POST | `/mail/refresh` | auth | Очистить кеш писем |
| GET | `/mail/test` | can_manage | Диагностика IMAP/SMTP |

**Credentials:** используются персональные (`user.mail_user`, `user.mail_password`) если заданы, иначе глобальные из config.

**Кеширование:** TTL 120 сек для списка, 3600 сек для тела письма. In-memory.

**Подпись при отправке:** HTML-подпись добавляется к body автоматически.

---

### 4.17 Backup / Archive (Admin)

| Метод | URL | Доступ | Описание |
|-------|-----|--------|----------|
| GET | `/admin/archive` | can_manage | Статистика БД |
| GET | `/admin/archive/export` | can_manage | Полный JSON-бэкап |
| GET | `/admin/archive/preview` | can_manage | JSON-превью бэкапа |
| POST | `/admin/archive/import` | super_admin | Импорт JSON-бэкапа (полная замена данных) |
| POST | `/admin/archive/migrate-review` | can_manage | review → done |

**Формат бэкапа:**
```json
{
  "exported_at": "...",
  "version": "2",
  "task_types": [...],
  "departments": [...],
  "users": [...],
  "tasks": [...],
  "attachments": [...],
  "comments": [...],
  "comment_attachments": [...],
  "time_logs": [...],
  "rhythms": [...],
  "plan_groups": [...],
  "plans": [...]
}
```

**Импорт:**
1. Очистить все таблицы (порядок для FK: time_logs → comment_attachments → comments → attachments → plans → plan_groups → rhythms → tasks → users → departments → task_types)
2. Вставить всё из JSON (bulk insert)
3. Второй проход: восстановить `parent_task_id` у задач
4. Сбросить PostgreSQL sequences: `setval('{table}_id_seq', max(id))`

---

## 5. Файловое хранилище

### 5.1 Локальное хранение
- Директория: настраивается через env `UPLOAD_FOLDER` (default: `/app/uploads`)
- Именование: `uuid4().hex + extension`
- Original name хранится в БД
- Лимит: 550 MB (MAX_CONTENT_LENGTH)
- Все типы файлов разрешены (ALLOWED_EXTENSIONS = null)

### 5.2 Яндекс Диск (интеграция)
- Если `YANDEX_DISK_TOKEN` задан → файлы загружаются на YDisk
- При ошибке YDisk → fallback на локальное хранение
- Функции: `upload_task_files`, `upload_comment_files`, `delete_file`, `delete_comment_files`
- Поля в БД: `yadisk_path`, `yadisk_url`, `yadisk_folder_url`

### 5.3 Аватары
- Директория: `static/avatars/`
- Формат: `{user_id}.png`, 256x256, crop center-square
- Fallback: pixel-art SVG (детерминистический, seed=user_id)

---

## 6. Авто-архивация

### При каждом запросе `/tasks` (канбан-доска):
- Debounce: не чаще 1 раза в час
- Архивировать задачи где: `status=done`, `completed_at < NOW()-7дней`, `is_archived=false`
- Устанавливать: `is_archived=true`, `archived_at=NOW()`

### CLI (cron, рекомендуется еженедельно):
- То же самое, без debounce

---

## 7. Временная зона

- Все datetime в БД в **UTC**
- Конвертация в локальное: `UTC + TZ_OFFSET_HOURS` (default: 3, МСК)
- `TZ_OFFSET_HOURS` задаётся через env
- Все периоды аналитики вычисляются в локальном времени, затем конвертируются в UTC для SQL-запросов

---

## 8. Справочные данные (seed)

### 8.1 Типы задач (начальные)

```json
[
  {"slug": "pub_images",          "label": "Картинки для публикаций"},
  {"slug": "banner",              "label": "Разработка баннера"},
  {"slug": "poster",              "label": "Разработка афиши"},
  {"slug": "presentation",        "label": "Разработка презентации"},
  {"slug": "presentation_update", "label": "Доработка презентации"},
  {"slug": "text_writing",        "label": "Написание текста"},
  {"slug": "handout",             "label": "Разработка раздатки"},
  {"slug": "placement",           "label": "Размещение материалов"},
  {"slug": "internal",            "label": "Внутренняя работа"},
  {"slug": "external",            "label": "Внешняя работа"},
  {"slug": "water_plants",        "label": "Полить цветы"},
  {"slug": "exports",             "label": "Подготовка выгрузок"},
  {"slug": "surveys",             "label": "Создание опросов"},
  {"slug": "photo_edit",          "label": "Обработка фото"},
  {"slug": "video_edit",          "label": "Монтаж ролика"},
  {"slug": "video_shoot",         "label": "Съёмка ролика"},
  {"slug": "photo_shoot",         "label": "Фотосъёмка"},
  {"slug": "meeting",             "label": "Планёрка"},
  {"slug": "mail_work",           "label": "Работа с почтой"},
  {"slug": "cloud_work",          "label": "Работа с облаками"},
  {"slug": "stand_design",        "label": "Разработка стендов"},
  {"slug": "pub_design",          "label": "Разработка дизайна для публикаций"},
  {"slug": "branded",             "label": "Разработка брендированной продукции"},
  {"slug": "small_design",        "label": "Мелкий дизайн"}
]
```

### 8.2 TYPE_LABELS (для аналитики)

Маппинг slug → человекочитаемая метка. Включает устаревшие типы:
```
"publication" → "Публикация (устар.)"
"picture"     → "Разработка картинки (устар.)"
"merch"       → "Сувенирная продукция (устар.)"
"other"       → "Другое"
null          → "Не указан"
```

### 8.3 AUTO_TAGS (авто-теги по типу задачи)

```json
{
  "pub_images": ["дизайн"],
  "banner": ["дизайн"],
  "poster": ["дизайн"],
  "presentation": ["дизайн"],
  "presentation_update": ["дизайн"],
  "text_writing": ["текст"],
  "handout": ["дизайн"],
  "stand_design": ["дизайн"],
  "pub_design": ["дизайн"],
  "branded": ["дизайн"],
  "small_design": ["дизайн"],
  "photo_edit": ["фото/видео"],
  "video_edit": ["фото/видео"],
  "video_shoot": ["фото/видео"],
  "photo_shoot": ["фото/видео"],
  "internal": ["внутреннее"],
  "external": ["внешнее"]
}
```

### 8.4 CARD_CHOICES (внешняя форма)

```json
[
  {"slug": "design",       "label": "Дизайн",               "tags": ["дизайн"]},
  {"slug": "photo_video",  "label": "Фото / Видео",         "tags": ["фото/видео"]},
  {"slug": "news",         "label": "Публикация новости",    "tags": ["публикация", "текст"]},
  {"slug": "event",        "label": "Освещение мероприятия",  "tags": ["фото/видео", "публикация"]},
  {"slug": "presentation", "label": "Презентации",           "tags": ["дизайн"]},
  {"slug": "forms",        "label": "Формы / Опросы",        "tags": ["внутреннее"]},
  {"slug": "verify",       "label": "Верификация",           "tags": ["внутреннее"]},
  {"slug": "card",         "label": "Создание открыток",     "tags": ["дизайн"]},
  {"slug": "other",        "label": "Другое",                "tags": []}
]
```

### 8.5 Начальные подразделения

```
IT отдел, Маркетинг, HR, Бухгалтерия, Производство
```

### 8.6 Начальный пользователь

```
username: admin, email: admin@tasktime.local, role: super_admin, password: admin123
```

---

## 9. Конфигурация (env-переменные)

| Переменная | Default | Описание |
|------------|---------|----------|
| `DATABASE_URL` | `postgresql://tasktime:tasktime@localhost:5432/tasktime` | |
| `SECRET_KEY` | `dev-secret-key-change-me` | JWT signing key |
| `UPLOAD_FOLDER` | `/app/uploads` | |
| `TZ_OFFSET_HOURS` | `3` | Смещение UTC → локальное |
| `YANDEX_DISK_TOKEN` | — | OAuth-токен Яндекс Диска |
| `MAIL_IMAP_HOST` | `mail.bmstu.ru` | |
| `MAIL_IMAP_PORT` | `993` | |
| `MAIL_SMTP_HOST` | `mail.bmstu.ru` | |
| `MAIL_SMTP_PORT` | `465` | |
| `MAIL_USER` | — | Глобальный IMAP/SMTP логин |
| `MAIL_PASSWORD` | — | Глобальный IMAP/SMTP пароль |
| `MAIL_FROM_EMAIL` | — | Email отправителя |
| `MAIL_FROM_NAME` | — | Имя отправителя |
| `MAIL_VERIFY_SSL` | `false` | Проверять SSL-сертификат |
| `MAIL_INBOX_FOLDER` | `info.kf` | IMAP-папка входящих |
| `MAIL_SENT_FOLDER` | `Sent` | IMAP-папка отправленных |
| `MAIL_SMTP_MODE` | `ssl` | `ssl` (порт 465) или `starttls` (порт 587) |

---

## 10. Рекомендуемая структура Go-проекта

```
backend/
├── cmd/
│   └── server/
│       └── main.go              -- точка входа, конфигурация, запуск Fiber
├── internal/
│   ├── config/
│   │   └── config.go            -- загрузка env
│   ├── db/
│   │   ├── db.go                -- pgxpool, подключение
│   │   └── migrations/          -- SQL-миграции
│   │       ├── 001_initial.sql
│   │       └── ...
│   ├── middleware/
│   │   ├── auth.go              -- JWT middleware
│   │   └── rbac.go              -- проверка ролей (can_admin, can_manage)
│   ├── model/
│   │   ├── user.go
│   │   ├── task.go
│   │   ├── time_log.go
│   │   ├── comment.go
│   │   ├── attachment.go
│   │   ├── rhythm.go
│   │   ├── plan.go
│   │   └── enums.go             -- Role, TaskStatus, Urgency, TaskTag
│   ├── handler/                 -- HTTP handlers (Fiber)
│   │   ├── auth.go
│   │   ├── tasks.go
│   │   ├── timer.go
│   │   ├── comments.go
│   │   ├── analytics.go
│   │   ├── admin.go
│   │   ├── profile.go
│   │   ├── public.go
│   │   ├── rhythms.go
│   │   ├── plans.go
│   │   ├── lists.go
│   │   ├── media_plan.go
│   │   ├── mail.go
│   │   └── uploads.go
│   ├── repo/                    -- SQL-запросы (pgx, без ORM)
│   │   ├── user_repo.go
│   │   ├── task_repo.go
│   │   ├── time_log_repo.go
│   │   ├── comment_repo.go
│   │   ├── analytics_repo.go
│   │   ├── rhythm_repo.go
│   │   ├── plan_repo.go
│   │   └── ...
│   ├── service/                 -- бизнес-логика
│   │   ├── auth_service.go
│   │   ├── task_service.go
│   │   ├── timer_service.go
│   │   ├── analytics_service.go
│   │   ├── archive_service.go
│   │   ├── mail_service.go
│   │   ├── yadisk_service.go
│   │   └── avatar_service.go
│   └── seed/
│       └── seed.go              -- начальные данные
├── pkg/
│   ├── jwt/
│   │   └── jwt.go
│   └── export/
│       ├── excel.go
│       └── pdf.go
├── uploads/                     -- volume для файлов
├── go.mod
├── go.sum
├── Dockerfile
└── docker-compose.yml
```

---

## 11. CLI-команды (аналоги)

Реализовать как подкоманды бинарника или отдельные утилиты:

| Команда | Описание |
|---------|----------|
| `server` | Запуск HTTP-сервера |
| `init-db` | Создать таблицы + seed |
| `migrate` | Запуск SQL-миграций |
| `auto-archive` | Архивация done-задач старше 7 дней |
| `fix-sequences` | Сброс PostgreSQL sequences |
| `archive-old` | Архивация done старше 365 дней |

---

## 12. Ключевые отличия от текущей реализации

| Аспект | Было (Flask) | Будет (Go + Fiber) |
|--------|-------------|-------------------|
| Аутентификация | Session + Cookie | JWT (access + refresh) |
| Шаблоны | Jinja2 (SSR) | REST API → Vue SPA |
| CSRF | Flask-WTF | Не нужен (JWT + SameSite cookie) |
| ORM | SQLAlchemy | Чистый SQL (pgx/sqlx) |
| Live-обновления | Polling /tasks/poll | WebSocket (рекомендуется) |
| Файлы | Flask send_file | Fiber c.SendFile / статика через nginx |
| Экспорт PDF | reportlab | go-pdf или wkhtmltopdf |
| Экспорт Excel | openpyxl | excelize |
| Password hash | werkzeug (pbkdf2) | bcrypt |
