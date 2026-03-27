# Frontend — Спецификация для Vue 3 + PrimeVue

> Полное описание frontend-части Groove Work для переписывания с Jinja2 SSR на Vue 3 SPA.
> UI-kit: PrimeVue 4 (Aura theme). Стилизация: Tailwind CSS 4.
> State management: Pinia. Роутинг: Vue Router 4.
> Сборка: Vite.

---

## 1. Глобальная архитектура

### 1.1 Общая структура

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts               -- маршруты + guards
│   ├── stores/                     -- Pinia stores
│   │   ├── auth.ts
│   │   ├── tasks.ts
│   │   ├── timer.ts
│   │   ├── ui.ts                   -- тема, сайдбар, модалки
│   │   └── notifications.ts
│   ├── api/                        -- HTTP-клиент (axios/fetch)
│   │   ├── client.ts               -- базовая конфигурация, interceptors
│   │   ├── auth.ts
│   │   ├── tasks.ts
│   │   ├── analytics.ts
│   │   ├── admin.ts
│   │   ├── lists.ts
│   │   ├── plans.ts
│   │   ├── rhythms.ts
│   │   ├── mail.ts
│   │   └── profile.ts
│   ├── composables/                -- переиспользуемая логика
│   │   ├── useTimer.ts
│   │   ├── usePeriod.ts
│   │   ├── useWebSocket.ts
│   │   ├── useDragDrop.ts
│   │   └── useFileUpload.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppSidebar.vue
│   │   │   ├── AppTopbar.vue
│   │   │   └── AppLayout.vue
│   │   ├── tasks/
│   │   │   ├── KanbanBoard.vue
│   │   │   ├── KanbanColumn.vue
│   │   │   ├── TaskCard.vue
│   │   │   ├── TaskForm.vue
│   │   │   ├── TaskDetail.vue
│   │   │   ├── TimerButton.vue
│   │   │   ├── CommentSection.vue
│   │   │   ├── SubtaskList.vue
│   │   │   └── DelegateDialog.vue
│   │   ├── analytics/
│   │   │   ├── DashboardStats.vue
│   │   │   ├── BurnupChart.vue
│   │   │   ├── TypeChart.vue
│   │   │   ├── DeptChart.vue
│   │   │   ├── StaffGrid.vue
│   │   │   ├── StaffDetailDialog.vue
│   │   │   └── TvSlide.vue
│   │   ├── plans/
│   │   │   ├── PlanCard.vue
│   │   │   └── PlanForm.vue
│   │   ├── rhythms/
│   │   │   ├── RhythmCard.vue
│   │   │   └── RhythmForm.vue
│   │   ├── media-plan/
│   │   │   ├── CalendarGrid.vue
│   │   │   ├── DayCell.vue
│   │   │   └── DayDialog.vue
│   │   ├── mail/
│   │   │   ├── MailList.vue
│   │   │   ├── MailMessage.vue
│   │   │   └── ComposeMail.vue
│   │   ├── admin/
│   │   │   ├── UserTable.vue
│   │   │   ├── UserForm.vue
│   │   │   └── BackupPanel.vue
│   │   ├── profile/
│   │   │   ├── AvatarCrop.vue
│   │   │   ├── ProfileStats.vue
│   │   │   └── ProfileForm.vue
│   │   └── shared/
│   │       ├── StatusBadge.vue
│   │       ├── UrgencyBadge.vue
│   │       ├── TagBadge.vue
│   │       ├── DurationLabel.vue
│   │       ├── PeriodNavigator.vue
│   │       ├── SearchableSelect.vue
│   │       ├── FileUpload.vue
│   │       └── ConfirmDialog.vue
│   ├── views/                      -- страницы (route components)
│   │   ├── LoginView.vue
│   │   ├── KanbanView.vue
│   │   ├── TaskDetailView.vue
│   │   ├── TaskFormView.vue
│   │   ├── AnalyticsDashboardView.vue
│   │   ├── AnalyticsTimeView.vue
│   │   ├── TvView.vue
│   │   ├── ProfileView.vue
│   │   ├── PlansView.vue
│   │   ├── RhythmsView.vue
│   │   ├── MediaPlanView.vue
│   │   ├── MailView.vue
│   │   ├── ListsView.vue
│   │   ├── AdminUsersView.vue
│   │   ├── AdminUserFormView.vue
│   │   ├── AdminArchiveView.vue
│   │   └── PublicSubmitView.vue
│   ├── types/                      -- TypeScript типы
│   │   ├── task.ts
│   │   ├── user.ts
│   │   ├── analytics.ts
│   │   └── enums.ts
│   └── utils/
│       ├── date.ts                 -- форматирование дат, TZ
│       ├── duration.ts             -- секунды → "2ч 15мин"
│       └── avatar.ts              -- генерация pixel-art SVG
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 2. Маршруты

| Путь | Компонент | Guard | Описание |
|------|-----------|-------|----------|
| `/login` | LoginView | guest | Авторизация |
| `/` | KanbanView | auth | Канбан-доска (redirect с /) |
| `/tasks` | KanbanView | auth | Канбан-доска |
| `/tasks/create` | TaskFormView | auth | Создание задачи |
| `/tasks/:id` | TaskDetailView | auth | Карточка задачи |
| `/tasks/:id/edit` | TaskFormView | auth | Редактирование |
| `/analytics` | AnalyticsDashboardView | auth | Дашборд |
| `/analytics/time` | AnalyticsTimeView | auth | Учёт времени |
| `/analytics/tv` | TvView | auth | TV-режим (полный экран) |
| `/profile` | ProfileView | auth | Профиль |
| `/plans` | PlansView | auth | Планы задач |
| `/rhythms` | RhythmsView | auth | Ритмы |
| `/media-plan` | MediaPlanView | auth | Медиаплан |
| `/mail` | MailView | auth | Почта |
| `/lists` | ListsView | can_manage | Списки (типы, подразделения) |
| `/admin/users` | AdminUsersView | can_manage | Пользователи |
| `/admin/users/create` | AdminUserFormView | can_manage | Создание пользователя |
| `/admin/users/:id/edit` | AdminUserFormView | can_manage | Редактирование |
| `/admin/archive` | AdminArchiveView | can_manage | Архив/бэкап |
| `/submit` | PublicSubmitView | — (public) | Внешняя форма заявок |

### Guards

- **guest**: только неавторизованные (редирект на `/` если залогинен)
- **auth**: требует JWT (редирект на `/login` если нет)
- **can_manage**: auth + роль admin/super_admin
- **can_admin**: auth + роль admin/super_admin/manager

---

## 3. Тема и стилизация

### 3.1 Цветовая система

**Хранение:** `localStorage` — ключи `tt-theme`, `tt-color`, `tt-glass`

**Режимы:** Light (по умолчанию) / Dark

**Основная палитра (CSS custom properties):**

```css
/* Статусы задач */
--color-new:         #94a3b8;   /* slate-400 */
--color-in-progress: #3b82f6;   /* blue-500 */
--color-paused:      #f59e0b;   /* amber-500 */
--color-done:        #22c55e;   /* green-500 */

/* Срочность */
--color-urgent:      #ef4444;   /* red-500 */
--color-important:   #f59e0b;   /* amber-500 */
--color-normal:      #3b82f6;   /* blue-500 */
--color-slow:        #94a3b8;   /* slate-400 */

/* Теги */
--tag-design:        #8b5cf6;   /* violet */
--tag-text:          #06b6d4;   /* cyan */
--tag-publication:   #f97316;   /* orange */
--tag-photo-video:   #ec4899;   /* pink */
--tag-internal:      #6b7280;   /* gray */
--tag-external:      #10b981;   /* emerald */

/* Рейтинг */
--rank-gold:         #eab308;
--rank-silver:       #94a3b8;
--rank-bronze:       #d97706;

/* Палитра графиков (8 цветов) */
--chart-1 through --chart-8
```

### 3.2 Типографика

- Системный шрифт: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- Моноширинный: для ID задач, slug-ов

### 3.3 Иконки

- **Bootstrap Icons** (`bi-*`): основные UI-иконки
- **Material Icons Round**: TV-режим
- Рекомендация: PrimeIcons (встроены в PrimeVue) + дополнительно Bootstrap Icons где нужно

### 3.4 Правила

- **Нет эмодзи** в интерфейсе
- Все даты в формате `dd.MM.yyyy HH:mm`
- Длительность: `Xч Yмин Zс` / `Xд Yч Zмин`

---

## 4. Layout — Основной каркас

### 4.1 AppLayout.vue

**Структура:**
```
┌─────────────────────────────────────────────┐
│ AppTopbar (sticky top)                      │
├──────────┬──────────────────────────────────┤
│          │                                  │
│ Sidebar  │  <router-view />                 │
│ (260px)  │  (main content)                  │
│          │                                  │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

- Sidebar: collapsible на мобильных (overlay)
- Topbar: активный таймер, аватар, тема

### 4.2 AppSidebar.vue

**Элементы:**
- Логотип + название "Groove Work"
- Версия (мелкий текст)
- Навигация:
  - Задачи (`/tasks`) — `bi-kanban`
  - Планы (`/plans`) — `bi-journal-text`
  - Ритмы (`/rhythms`) — `bi-arrow-repeat`
  - Медиаплан (`/media-plan`) — `bi-calendar3`
  - Аналитика (`/analytics`) — `bi-graph-up`
  - Учёт времени (`/analytics/time`) — `bi-clock-history`
  - Почта (`/mail`) — `bi-envelope`
  - --- (разделитель, только для can_manage) ---
  - Списки (`/lists`) — `bi-list-ul`
  - Пользователи (`/admin/users`) — `bi-people`
  - Архив (`/admin/archive`) — `bi-archive`
- Активный пункт: выделение фоном
- Скрывать пункты по ролям (can_manage, can_admin)

### 4.3 AppTopbar.vue

**Элементы:**
- Кнопка toggle sidebar (мобильные)
- **Активный таймер** (если есть):
  - Название задачи (ссылка)
  - Тикающий счётчик (hh:mm:ss, обновляется каждую секунду)
  - Кнопка "Пауза"
- Spacer
- Кнопка создания задачи (`+`)
- Toggle темы (light/dark)
- Аватар + dropdown:
  - Профиль
  - Выход

---

## 5. Страницы — детальное описание

### 5.1 LoginView

**Компонент:** центрированная карточка

**Поля:**
- Username — `InputText`
- Password — `Password`
- Кнопка "Войти" — `Button`

**Логика:**
- `POST /api/auth/login` → сохранить tokens в `authStore`
- При роли `tv` → redirect на `/analytics/tv`
- Иначе → redirect на `/tasks`
- Flash-сообщение при ошибке

**Стиль:** градиентный фон, glassmorphism карточка, логотип сверху

---

### 5.2 KanbanView (Канбан-доска)

**Основной экран приложения.**

#### Компоненты:
- `KanbanBoard` → 4 × `KanbanColumn` → N × `TaskCard`

#### KanbanBoard

**Toolbar:**
- Toggle сортировки новых (`sort_new`)
- Кнопка "Создать задачу" → `/tasks/create`
- Кнопка "Архивировать все готовые" (can_admin)

**Layout:** горизонтальный скролл, 4 колонки:
1. **Новые** (new) — делится на 2 секции: "Заявки" (is_external) и "Задачи"
2. **В работе** (in_progress)
3. **На паузе** (paused)
4. **Готово** (done) — показывает и archived done

**Mobile:** табы вместо колонок, переключение свайпом или кнопками

#### KanbanColumn

- Заголовок: цветная точка + название + счётчик
- Drag-and-drop зона
- Визуальная обратная связь при drag-over

**Drag-and-drop правила:**
- Нельзя drag archived задачи
- Нельзя drag задачи, взятые другим пользователем (если не can_admin)
- Нельзя drop в `in_progress` (только через таймер)
- Нельзя drop `is_external` без `task_type` → показать toast "Укажите тип"
- При drop: `POST /api/tasks/:id/move {status}`

#### TaskCard

**Визуальные элементы:**
| Элемент | Условие | Расположение |
|---------|---------|--------------|
| Urgency badge | всегда | верхний левый угол |
| "Архив" chip | is_archived | рядом с urgency |
| Tags | если есть | строка бейджей |
| Task ID | всегда | мелкий текст `#123` |
| Title | всегда | основной текст (жирный) |
| Overdue indicator | is_overdue | красная метка |
| Department | если есть | мелкий текст |
| Deadline | если есть | дата (красная если просрочен) |
| Parent task link | если parent_task_id | ссылка "↑ Родительская" |
| Pub date | если dynamic_fields.pub_date | дата публикации |
| Duration | total_seconds > 0 | "2ч 15мин" |
| Assignee | если assigned_to | аватар + имя |
| Timer button | см. ниже | нижний правый |

**Кнопка таймера на карточке:**
| Состояние | Кнопка | Цвет |
|-----------|--------|------|
| Свободна, пользователь без таймера | ▶ Старт | зелёный |
| Мой таймер на этой задаче | ⏸ Пауза | жёлтый |
| Взята другим | — (нет кнопки) | — |
| External без task_type | "Указать тип" | серый |
| Свободна, но у меня таймер на другой | ▶ Старт | зелёный (покажет conflict dialog) |

**Клик по карточке:** переход на `/tasks/:id`

#### TimerButton (composable: useTimer)

**Логика взаимодействия:**

1. Клик "Старт" → `POST /api/tasks/:id/timer/start`
2. Ответ `{taken: true}` → Toast: "Задача взята: {имя}"
3. Ответ `{conflict: true}` → Dialog: "У вас уже запущен таймер на «{title}». Переключить?"
   - "Да" → `POST /api/tasks/:id/timer/force-start`
   - "Нет" → отмена
4. Ответ `{error: "need_task_type"}` → redirect на `/tasks/:id/edit`
5. Ответ `{success: true}` → обновить карточку + topbar

**Polling / WebSocket:**
- Текущая реализация: `GET /api/tasks/poll` каждые 10 сек
- Рекомендация: WebSocket для реального времени
- При изменении статуса задачи — переотрисовать карточку

---

### 5.3 TaskDetailView

**Секции страницы:**

#### 1. Header
- Breadcrumb: Задачи > #123
- Заголовок задачи (крупный)
- Бейджи: статус, срочность, просрочено, архив, теги
- Кнопки действий:
  - "Редактировать" → `/tasks/:id/edit`
  - "Удалить" (can_admin) → ConfirmDialog
  - "Разархивировать" (can_admin, если archived)

#### 2. Parent/Subtask navigation
- Ссылка на родительскую задачу (если есть)
- Список подзадач с иконками статуса
- Счётчик открытых подзадач
- Кнопка "Добавить подзадачу" → `/tasks/create?parent_id=:id`

#### 3. Assignment section
- Текущий исполнитель (аватар + имя)
- Бейдж "Вы" если assigned_to == current_user
- Кнопка "Делегировать" → DelegateDialog
- Кнопка "Вернуть в пул" → ConfirmDialog (unassign)
- Показывается только для assigned_to/can_admin

#### 4. Details grid (2 колонки)
| Поле | Отображение |
|------|-------------|
| Заказчик | ФИО, телефон (ссылка tel:), email (ссылка mailto:) |
| Подразделение | название |
| Тип задачи | label из task_types |
| Дедлайн | дата (красная если просрочен) |
| Создана | дата + автор |
| Общее время | "2ч 15мин" |

Для публикаций дополнительно:
- Дата публикации
- Площадки
- Ссылка на публикацию

#### 5. Attachments
- Список файлов: иконка типа, имя, кнопка скачивания
- Кнопка "Скачать все (ZIP)"
- Кнопка удаления (×) для каждого файла
- Если файл на YDisk — показать ссылку

#### 6. Timer & Time logs
- Кнопка таймера (большая, по центру)
- "Закрыть задачу" (если можно: нет открытых подзадач)
- История таймера (таблица):
  - Сотрудник, начало, конец, длительность
  - Активные таймеры выделены (пульсирующий индикатор)

#### 7. Comments (CommentSection)
- Список комментариев (снизу вверх по дате)
- Каждый комментарий:
  - Аватар + имя + дата
  - Текст
  - Вложения (чипы с кнопкой скачивания)
  - Кнопка удаления (автор/can_admin)
- Форма добавления:
  - Textarea
  - FileUpload (множественный)
  - Кнопка "Отправить"
  - Лимит: 100 МБ суммарно

#### DelegateDialog
- Dropdown с активными пользователями (кроме tv)
- Кнопка "Делегировать"
- `POST /api/tasks/:id/delegate {user_id}`

---

### 5.4 TaskFormView

**Режимы:** создание / редактирование

**Переключатель режима (только создание):**
- "Задача" — обычная форма
- "Публикация" — режим создания публикации (3 задачи)

#### Основная форма (режим "Задача")

| Поле | Компонент PrimeVue | Обязательность |
|------|--------------------|----------------|
| Название | InputText | обязательно |
| Описание | Textarea | нет |
| Тип задачи | Select (searchable) | обязательно |
| Срочность | SelectButton (4 варианта) | default: normal |
| Теги | MultiSelect / Checkbox group | нет |
| Подразделение | Select (searchable) | нет |
| Заказчик ФИО | InputText | нет |
| Телефон | InputText | нет |
| Email | InputText | нет |
| Дедлайн | DatePicker (datetime) | нет |
| Уточнение | Textarea | нет |
| Дата мероприятия | DatePicker | нет |
| Родительская задача | hidden (из query param) | нет |
| Файлы | FileUpload (multiple) | нет |

**Динамические поля по типу:**
- Тип `publication`/`placement` → показать: подтип, площадки, дата публикации, URL
- Остальные типы → показать: уточнение, дата мероприятия

#### Режим "Публикация"

Создаёт 3 связанные задачи.

**Дополнительные поля:**
- Дата публикации (`datetime-local`)
- Площадки (чекбоксы): Сайт, Внешние соц. сети, Внутренние соц. сети, Афиша
- Кнопка "Выбрать все"

**Visual hint:** предупреждение "Будут созданы 3 задачи: родительская + Картинки + Текст"

#### Загрузка файлов

- Drag-and-drop зона
- Список выбранных файлов с размерами
- Кнопка удаления для каждого
- Прогресс-бар при загрузке
- Индикатор общего размера

#### Типы задач

Загружаются из API: `GET /api/task-types` → массив `[{value, label}]`

---

### 5.5 AnalyticsDashboardView

**Toolbar:** период (табы): День / Неделя / Месяц / Год

**Grid layout (responsive):**

```
┌──────────┬──────────┬──────────┬──────────┐
│  Новые   │ В работе │ На паузе │  Готово  │  ← StatCards (4 колонки)
└──────────┴──────────┴──────────┴──────────┘
┌────────────────────────────────────────────┐
│         Burn-up Chart (line)               │  ← Created vs Done
└────────────────────────────────────────────┘
┌──────────────┬──────────────┬──────────────┐
│  По отделам  │  По типам    │ Топ по       │
│  (bar chart) │  (h-bar)     │ времени      │
└──────────────┴──────────────┴──────────────┘
┌────────────────────────────────────────────┐
│   Топ по закрытым задачам (таблица)        │
└────────────────────────────────────────────┘
```

**Графики (Chart.js или PrimeVue Charts):**

1. **BurnupChart** — линейный: 2 линии (созданные нарастающим итогом, закрытые)
2. **DeptChart** — вертикальный bar, до 8 отделов
3. **TypeChart** — горизонтальный bar, динамическая высота (30px × кол-во типов)
4. **Топ по времени** — таблица: место, имя, часы
5. **Топ по задачам** — таблица: место, имя, кол-во

**Stacked bar (по типам и отделам):**
- 4 сегмента по статусам (new / in_progress / paused / done)
- Tooltip с деталями

---

### 5.6 AnalyticsTimeView

**Toolbar:**
- Табы: День / Неделя / Месяц
- PeriodNavigator: `< [дата] >` (offset-based)
- DatePicker для быстрого перехода к конкретной дате

**StaffGrid (responsive, 1-4 колонки):**

Каждая карточка сотрудника:
```
┌─────────────────────────────┐
│  [Avatar]  Имя Фамилия      │
│  Закрыто: 12 задач          │
│  Время: 8ч 30мин            │
│  ████████████░░ 72 балла #3 │
│  Нажмите для деталей        │
└─────────────────────────────┘
```

**Клик по карточке → StaffDetailDialog:**
- Имя, период
- Кнопка "Экспорт Excel"
- 2 таба:
  - **Задачи**: таблица (ID, заголовок, дата, время)
  - **По типам**: тип, кол-во, время, progress bar

**Права:**
- `staff` видит только свою карточку
- `can_admin` видит всех

---

### 5.7 TvView (полноэкранный режим)

**Layout:** полный экран, без sidebar/topbar

**Элементы управления:**
- Верхняя панель: логотип, часы (обновляются каждую секунду), toggle темы
- Стрелки навигации (появляются при наведении)
- Автопереключение слайдов каждые 30 сек

**5 слайдов:**

| # | Название | Контент |
|---|----------|---------|
| 1 | Сегодня — Статусы | 3 stat-карточки (новые, в работе, готово) + типы задач (h-bar) + общее время |
| 2 | Сегодня — Отделы | Donut chart по отделам + рейтинг сотрудников (top-5) |
| 3 | Неделя — Статусы | Аналогично слайду 1 но за неделю |
| 4 | Неделя — Отделы | Аналогично слайду 2 но за неделю |
| 5 | Всё время | Общая статистика (новые/в работе/готово) + типы + отделы + рейтинг за год |

**Рейтинг:** строки с аватарами, баллами, бейджами места (золото/серебро/бронза)

**Data source:** `GET /api/analytics/tv/data` каждые 30 сек

---

### 5.8 ProfileView

**Секции:**

#### 1. Avatar + Info
- Большой аватар (128px) с overlay "Загрузить"
- Имя, @username, роль, дата регистрации
- Кнопка "Сбросить аватар"

#### 2. AvatarCrop dialog
- Canvas 300x300 с круглой маской
- Pan: drag мышью / touch
- Zoom: колесо мыши / pinch
- Кнопки: "Сохранить" / "Отмена"
- Результат: 256x256 PNG, crop center-square

#### 3. Quick stats (4 колонки)
- Создано задач (за всё время)
- Закрыто задач
- Время за неделю
- Время за месяц

#### 4. ProfileStats
- PeriodNavigator (день/неделя/месяц)
- Сводка: задач, время, балл, место
- Таблица по типам с progress bar
- Кнопка "Все задачи за период" → dialog

#### 5. ProfileForm
- Полное имя (InputText)
- Пароль (Password, необязательный)
- Кнопка "Сохранить"

#### 6. Почтовые настройки
- mail_user (InputText)
- mail_password (Password)
- Кнопки "Сохранить" / "Очистить"

---

### 5.9 PlansView

**Toolbar:**
- Кнопка "Создать план"
- Кнопка "Создать группу"
- Фильтр по группам (табы/чипы с счётчиками)

**Grid (responsive, auto-fill 300px min):**

PlanCard:
```
┌─────────────────────────────────┐
│ [urgency] [tags]          #42   │
│ Заголовок плана                 │
│ Описание (2 строки max)...      │
│                                 │
│ 📅 Дата выпуска: 15.04.2025    │
│ Тип: Баннер  |  Отдел: IT      │
│                                 │
│ [Реализовать] [✏️] [🗑️]        │
└─────────────────────────────────┘
```

**Дата выпуска — цветовая индикация:**
- Скоро (< 3 дней) → жёлтый
- Сегодня → зелёный
- Просрочена → красный
- Не задана → серый

**"Реализовать"** (`POST /api/plans/:id/push`):
- Подтверждение: "Создать задачу из плана? План будет удалён."
- Создаёт задачу (+ подзадачи для publication)
- Redirect на `/tasks/:new_task_id`

**PlanForm (dialog):**
- Те же поля что у TaskForm + release_date + group_id
- Режимы: создание / редактирование

---

### 5.10 RhythmsView

**Grid (responsive, 1-3 колонки):**

RhythmCard:
```
┌─────────────────────────────────┐
│ Название ритма          [вкл/⏻] │
│ Описание                        │
│                                 │
│ 🔄 Еженедельно (Пн) в 09:00   │
│ ⚡ Готово к запуску!             │
│                                 │
│ → Задача: "Полить цветы"       │
│   Тип: internal | Теги: [внутр] │
│                                 │
│ Последний запуск: 21.03 09:00   │
│ [▶ Запустить] [✏️] [🗑️]        │
└─────────────────────────────────┘
```

**"Готово к запуску"** — показывается если `is_due=true` (вычисляется на backend)

**RhythmForm (dialog):**
| Поле | Компонент |
|------|-----------|
| Название | InputText (required) |
| Описание | Textarea |
| Частота | Select: daily/weekly/monthly |
| День недели | Select (0-6, показывается при weekly) |
| День месяца | InputNumber (1-31, показывается при monthly) |
| Время | InputText "HH:MM" |
| Тип задачи | Select (из /api/task-types, required) |
| Теги | MultiSelect / Checkbox group |
| Срочность | SelectButton |
| Подразделение | Select |
| Активен | Toggle |

---

### 5.11 MediaPlanView

**Toolbar:**
- Навигация по месяцам: `< Март 2025 >`
- Кнопка "Создать публикацию" → `/tasks/create?mode=publication`
- Кнопка "Экспорт Excel"

**CalendarGrid:**
```
┌────┬────┬────┬────┬────┬────┬────┐
│ Пн │ Вт │ Ср │ Чт │ Пт │ Сб │ Вс │
├────┼────┼────┼────┼────┼────┼────┤
│    │    │  1 │  2 │  3 │  4 │  5 │
│    │    │ ■■ │    │ ■  │    │    │
├────┼────┼────┼────┼────┼────┼────┤
...
```

**DayCell:**
- Число месяца
- Фишки публикаций (время + укороченное название)
- Цвет фишки = цвет статуса
- Выходные: серый фон
- Сегодня: подсветка

**Клик по ячейке → DayDialog:**
- Дата, список публикаций
- Каждая строка: время, заголовок, статус, площадки, ссылка

**Мобильный режим:** agenda-вид (список дней с количеством публикаций)

**Выборка данных:** задачи с `task_type IN ('placement', 'publication')`, `is_archived=false`

---

### 5.12 MailView

**Split layout:**
```
┌──────────────┬──────────────────────────────┐
│  MailList     │  MailMessage                 │
│  (340px)     │  (flex)                      │
│              │                              │
│  [Search]    │  Subject                     │
│  ─────────── │  From / To / Date            │
│  ● Тема 1   │  ─────────────────────────── │
│    От кого   │                              │
│    12:30     │  Тело письма                 │
│  ─────────── │                              │
│    Тема 2   │  📎 Вложения                 │
│              │                              │
└──────────────┴──────────────────────────────┘
```

**MailList:**
- Табы: Входящие / Отправленные
- Кнопка обновления
- Кнопка "Написать" → ComposeMail dialog
- Список: sender, subject, date, unread dot
- Пагинация (30 на страницу)
- Кеширование: не обновлять чаще 2 мин

**MailMessage:**
- Заголовок: тема, от/кому/дата/cc
- Тело: HTML (iframe для безопасности) или plain text
- Вложения: чипы с кнопкой скачивания
- Кнопка "Ответить" → ComposeMail с prefill

**ComposeMail (dialog):**
- To (InputText)
- Cc (InputText)
- Subject (InputText)
- Body (Textarea)
- Attachments (FileUpload)
- "Отправить" → `POST /api/mail/send`

**Мобильный:** список на полную ширину, клик открывает сообщение

---

### 5.13 ListsView

**Табы:** Типы задач / Подразделения

#### Типы задач

**Таблица (DataTable):**
| Slug (badge) | Название | Действия |
|---|---|---|
| `banner` | Разработка баннера | ✏️ 🗑️ |

- Кнопка "Добавить тип" → Dialog: slug + label
- Кнопка "Экспорт JSON"
- Кнопка "Импорт JSON" → FileUpload dialog

**CRUD:** `POST/PUT/DELETE /api/lists/task-types[/:id]` — JSON, без перезагрузки

#### Подразделения

**Таблица:**
| Название | Руководитель | Действия |
|---|---|---|
| IT отдел | Иванов И.И. | ✏️ 🗑️ |

- CRUD: `/api/lists/departments[/:id]`
- Экспорт/Импорт JSON

---

### 5.14 AdminUsersView

**Таблица (DataTable):**
| Аватар | Имя | Логин | Email | Роль | Статус | Действия |
|---|---|---|---|---|---|---|
| [img] | Иванов | `ivanov` | ... | Сотрудник | 🟢 Активен | ✏️ 🗑️ |

- Кнопка "Добавить пользователя" → `/admin/users/create`
- Счётчик пользователей
- Роль отображается бейджем с цветом
- Нельзя удалить super_admin
- Нельзя редактировать super_admin (если не super_admin)

---

### 5.15 AdminUserFormView

**Поля:**
| Поле | Компонент | Валидация |
|------|-----------|-----------|
| Полное имя | InputText | required |
| Логин | InputText | 4+ символов, `^[A-Za-z][A-Za-z0-9_-]{3,}$` |
| Email | InputText | required, email format |
| Пароль | Password | 6+ символов (required при создании) |
| Роль | Select | ограничен правами текущего пользователя |
| Активен | ToggleSwitch | нельзя деактивировать себя |

**Доступные роли в select:**
- Если current_user = `super_admin`: все роли
- Если current_user = `admin`: manager, staff, tv

---

### 5.16 AdminArchiveView

**Секции:**

#### 1. Stats grid (6 карточек)
- Пользователи, Задачи, Комментарии, Тайм-логи, Вложения, Подразделения

#### 2. Migrate review (если есть задачи со статусом review)
- Предупреждение + кнопка

#### 3. Export
- Кнопка "Скачать JSON"
- Кнопка "Предпросмотр" → модалка с JSON

#### 4. Import (только super_admin)
- Красное предупреждение: "Все текущие данные будут заменены!"
- FileUpload для JSON
- Двойное подтверждение

---

### 5.17 PublicSubmitView (без авторизации)

**Multi-step wizard (2 экрана + экран успеха):**

#### Экран 1: Информация о заявителе
- Подразделение (Select с поиском)
- ФИО (required)
- Телефон
- Email
- Описание проблемы (Textarea)
- Progress bar: 50%
- "Далее →"

#### Экран 2: Классификация
- Карточки выбора (grid 3 колонки):
  - Дизайн, Фото/Видео, Публикация новости, Освещение мероприятия, Презентации, Формы/Опросы, Верификация, Создание открыток, Другое
  - Каждая с иконкой (Bootstrap Icons)
  - При выборе → подсветка
- Название задачи (InputText, required)
- Описание (Textarea)
- Файлы (FileUpload drag-drop)
- Progress bar: 100%
- "Отправить"

#### Экран успеха
- Иконка галочки
- "Заявка отправлена!"
- Кнопка "Создать ещё" (prefill данных экрана 1)
- Кнопка "Новая заявка" (чистая форма)

**Route:** не требует JWT. Отдельный layout без sidebar.

---

## 6. Shared компоненты

### 6.1 StatusBadge
- Props: `status: 'new' | 'in_progress' | 'paused' | 'done'`
- Цвет фона + текст

### 6.2 UrgencyBadge
- Props: `urgency: 'slow' | 'normal' | 'important' | 'urgent'`
- Цвет + текст: Неспешно / Обычно / Важно / Срочно

### 6.3 TagBadge
- Props: `tag: string`
- Цвета: дизайн=violet, текст=cyan, публикация=orange, фото/видео=pink, внутреннее=gray, внешнее=emerald

### 6.4 DurationLabel
- Props: `seconds: number`
- Вывод: `0 мин` / `Xs` / `Xмин Yс` / `Xч Yмин` / `Xд Yч Zмин`

### 6.5 PeriodNavigator
- Props: `mode, offset, label`
- Emits: `@prev`, `@next`, `@pick-date(date)`
- Кнопки `<` `>` + метка периода + date picker

### 6.6 SearchableSelect
- Props: `options[], modelValue, placeholder`
- Dropdown с текстовым поиском
- Или использовать PrimeVue `Select` с `filter` prop

### 6.7 FileUpload
- Drag-and-drop зона
- Список файлов с размерами
- Кнопка удаления
- Progress bar
- Max size indication

### 6.8 ConfirmDialog
- Props: `header, message, acceptLabel, rejectLabel, severity`
- Использовать PrimeVue `ConfirmDialog` service

---

## 7. Stores (Pinia)

### 7.1 authStore

```ts
interface AuthState {
  user: User | null
  accessToken: string | null
}

// Actions:
login(username, password) → set tokens + user
logout() → clear tokens
refreshToken() → update accessToken

// Getters:
isAuthenticated: boolean
canAdmin: boolean       // super_admin | admin | manager
canManage: boolean      // super_admin | admin
isSuperAdmin: boolean
```

### 7.2 tasksStore

```ts
interface TasksState {
  tasks: Task[]
  loading: boolean
  sortNewByUpdated: boolean
}

// Actions:
fetchTasks()
moveTask(taskId, status)
deleteTask(taskId)

// Getters:
tasksByStatus(status): Task[]
externalTasks: Task[]     // is_external, status=new
internalTasks: Task[]     // !is_external, status=new
```

### 7.3 timerStore

```ts
interface TimerState {
  activeTimer: { taskId: number, startedAt: string } | null
  elapsedSeconds: number   // обновляется каждую секунду
}

// Actions:
startTimer(taskId)
forceStartTimer(taskId)
pauseTimer(taskId)
fetchMyTimer()
tick()                   // +1 сек, вызывается setInterval

// Getters:
isTimerRunning: boolean
activeTaskId: number | null
formattedElapsed: string  // "01:23:45"
```

### 7.4 uiStore

```ts
interface UiState {
  theme: 'light' | 'dark'
  sidebarOpen: boolean
  sidebarCollapsed: boolean
}

// Actions:
toggleTheme()
toggleSidebar()
```

---

## 8. API-клиент

### 8.1 Базовая конфигурация

```ts
// api/client.ts
const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// Request interceptor: добавить Authorization header
api.interceptors.request.use(config => {
  const token = authStore.accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response interceptor: 401 → попытка refresh → если не удалось → logout
api.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      try {
        await authStore.refreshToken()
        return api(error.config)  // retry
      } catch {
        authStore.logout()
        router.push('/login')
      }
    }
    return Promise.reject(error)
  }
)
```

### 8.2 Обработка ошибок

- Toast-уведомления для ошибок (PrimeVue `Toast`)
- Форм-валидация: подсветка полей
- 403 → "Недостаточно прав"
- 404 → redirect на 404 page
- 500 → "Ошибка сервера"

---

## 9. Composables

### 9.1 useTimer

```ts
function useTimer() {
  // Отслеживает активный таймер
  // setInterval для тикания счётчика
  // Методы: start, forceStart, pause
  // Обработка conflict/taken ответов
}
```

### 9.2 usePeriod

```ts
function usePeriod(defaultMode = 'week') {
  // mode: ref('day' | 'week' | 'month')
  // offset: ref(number)
  // label: computed(string)  // "24.03 – 30.03.2025"
  // prev(), next(), pickDate(date)
  // startUtc, endUtc: computed
}
```

### 9.3 useWebSocket (рекомендация)

```ts
function useWebSocket() {
  // Подключение к ws://.../ws
  // Events: task_updated, timer_started, timer_stopped
  // Автопереподключение
  // Замена polling
}
```

### 9.4 useDragDrop

```ts
function useDragDrop() {
  // Обработка drag start/over/drop
  // Валидация drop targets
  // Визуальная обратная связь
}
```

---

## 10. Утилиты

### 10.1 date.ts

```ts
const TZ_OFFSET = 3  // из config

formatDateTime(utc: string): string    // "28.03.2025 14:30"
formatDate(utc: string): string        // "28.03.2025"
formatShort(utc: string): string       // "28.03 14:30"
formatTime(utc: string): string        // "14:30"
toLocalDate(utc: string): Date
```

### 10.2 duration.ts

```ts
formatDuration(seconds: number): string
// 0         → "0 мин"
// 45        → "45с"
// 125       → "2мин 5с"
// 3725      → "1ч 2мин"
// 90061     → "1д 1ч 1мин"
```

### 10.3 avatar.ts

```ts
generatePixelArtSvg(userId: number, size = 64): string
// Детерминистический 8×8 pixel-art SVG
// Seed = userId
// Symmetric horizontal (4 cols → mirror)
// HSL color from seed
```

---

## 11. Адаптивность (breakpoints)

| Размер | Ширина | Поведение |
|--------|--------|-----------|
| Mobile | < 640px | Sidebar overlay, одна колонка канбана, agenda вместо календаря |
| Tablet | 640-1024px | Sidebar collapsed, 2 колонки канбана, сетки 2 колонки |
| Desktop | 1024-1280px | Sidebar expanded, 4 колонки канбана, сетки 3 колонки |
| Wide | > 1280px | Полный layout, сетки 4 колонки |

---

## 12. PrimeVue компоненты (маппинг)

| Текущий UI-элемент | PrimeVue компонент |
|---|---|
| Text input | InputText |
| Password | Password |
| Textarea | Textarea |
| Select (searchable) | Select (с filter) |
| Multi-select | MultiSelect |
| Checkbox group | Checkbox (в цикле) |
| Radio buttons | RadioButton / SelectButton |
| Toggle | ToggleSwitch |
| Date picker | DatePicker |
| File upload | FileUpload |
| Table | DataTable |
| Modal/Dialog | Dialog |
| Confirm | ConfirmDialog (service) |
| Toast | Toast (service) |
| Tabs | Tabs / TabList / Tab / TabPanels |
| Badge | Badge / Tag |
| Button | Button |
| Menu | Menu / TieredMenu |
| Tooltip | Tooltip (directive) |
| Progress bar | ProgressBar |
| Skeleton | Skeleton |
| Avatar | Avatar |
| Chip | Chip |
| Card | Card |
| Divider | Divider |
| Breadcrumb | Breadcrumb |
| Chart | Chart (Chart.js wrapper) |

---

## 13. Отличия от текущего фронтенда

| Аспект | Было (Jinja2 SSR) | Будет (Vue SPA) |
|--------|-------------------|-----------------|
| Рендеринг | Сервер (HTML) | Клиент (SPA) |
| Навигация | Full page reload | Vue Router (SPA transitions) |
| Формы | HTML form + POST | JSON API + реактивные формы |
| CSRF | Token в формах | Не нужен (JWT) |
| Стили | Inline CSS + DaisyUI CDN | Tailwind 4 + PrimeVue Aura |
| Модалки | `<dialog>` native | PrimeVue Dialog service |
| Графики | Chart.js прямой | PrimeVue Chart (обёртка Chart.js) |
| Live updates | Polling (10 сек) | WebSocket (рекомендация) |
| Тема | localStorage + CSS vars | Pinia store + PrimeVue theming |
| Иконки | Bootstrap Icons CDN | PrimeIcons + Bootstrap Icons |
| Файлы | multipart form submit | FileUpload компонент + API |
