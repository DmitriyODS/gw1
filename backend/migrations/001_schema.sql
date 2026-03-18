-- ================================================================
-- GW1 Backend Schema
-- ================================================================

CREATE TYPE user_role AS ENUM ('super_admin', 'manager', 'admin', 'staff', 'tv');
CREATE TYPE task_status AS ENUM ('new', 'in_progress', 'paused', 'done');
CREATE TYPE urgency_level AS ENUM ('slow', 'normal', 'important', 'urgent');
CREATE TYPE rhythm_frequency AS ENUM ('daily', 'weekly', 'monthly');

-- ----------------------------------------------------------------
CREATE TABLE departments (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- ----------------------------------------------------------------
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL DEFAULT '',
    role          user_role NOT NULL DEFAULT 'staff',
    is_active     BOOLEAN NOT NULL DEFAULT true,
    avatar_path   VARCHAR(500),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE tasks (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(500) NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    status          task_status NOT NULL DEFAULT 'new',
    urgency         urgency_level NOT NULL DEFAULT 'normal',
    task_type       VARCHAR(100),
    tags            TEXT[] NOT NULL DEFAULT '{}',
    dynamic_fields  JSONB NOT NULL DEFAULT '{}',
    customer_name   VARCHAR(255),
    customer_phone  VARCHAR(50),
    customer_email  VARCHAR(255),
    deadline        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    department_id   INT REFERENCES departments(id) ON DELETE SET NULL,
    created_by_id   INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    assigned_to_id  INT REFERENCES users(id) ON DELETE SET NULL,
    parent_task_id  INT REFERENCES tasks(id) ON DELETE CASCADE,
    is_archived     BOOLEAN NOT NULL DEFAULT false,
    archived_at     TIMESTAMPTZ
);

CREATE INDEX idx_tasks_status       ON tasks(status);
CREATE INDEX idx_tasks_is_archived  ON tasks(is_archived);
CREATE INDEX idx_tasks_urgency      ON tasks(urgency);
CREATE INDEX idx_tasks_deadline     ON tasks(deadline);
CREATE INDEX idx_tasks_assigned_to  ON tasks(assigned_to_id);
CREATE INDEX idx_tasks_department   ON tasks(department_id);
CREATE INDEX idx_tasks_parent       ON tasks(parent_task_id);

-- ----------------------------------------------------------------
CREATE TABLE task_attachments (
    id            SERIAL PRIMARY KEY,
    task_id       INT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    filename      VARCHAR(500) NOT NULL,
    original_name VARCHAR(500) NOT NULL,
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE task_comments (
    id            SERIAL PRIMARY KEY,
    task_id       INT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id       INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    text          TEXT NOT NULL DEFAULT '',
    filename      VARCHAR(500),
    original_name VARCHAR(500),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE time_logs (
    id         SERIAL PRIMARY KEY,
    task_id    INT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id    INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at   TIMESTAMPTZ
);

CREATE INDEX idx_time_logs_task   ON time_logs(task_id);
CREATE INDEX idx_time_logs_user   ON time_logs(user_id);
CREATE INDEX idx_time_logs_active ON time_logs(ended_at) WHERE ended_at IS NULL;

-- ----------------------------------------------------------------
CREATE TABLE rhythms (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(255) NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    frequency        rhythm_frequency NOT NULL,
    day_of_week      SMALLINT CHECK (day_of_week BETWEEN 0 AND 6),
    day_of_month     SMALLINT CHECK (day_of_month BETWEEN 1 AND 31),
    task_title       VARCHAR(500) NOT NULL,
    task_description TEXT NOT NULL DEFAULT '',
    task_urgency     urgency_level NOT NULL DEFAULT 'normal',
    task_type        VARCHAR(100),
    task_tags        TEXT[] NOT NULL DEFAULT '{}',
    department_id    INT REFERENCES departments(id) ON DELETE SET NULL,
    created_by_id    INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    is_active        BOOLEAN NOT NULL DEFAULT true,
    last_run_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE plan_groups (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(255) NOT NULL,
    created_by_id INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE plans (
    id               SERIAL PRIMARY KEY,
    title            VARCHAR(500) NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    customer_name    VARCHAR(255),
    customer_phone   VARCHAR(50),
    customer_email   VARCHAR(255),
    release_date     TIMESTAMPTZ,
    task_type        VARCHAR(100),
    urgency          urgency_level NOT NULL DEFAULT 'normal',
    tags             TEXT[] NOT NULL DEFAULT '{}',
    dynamic_fields   JSONB NOT NULL DEFAULT '{}',
    group_id         INT REFERENCES plan_groups(id) ON DELETE SET NULL,
    department_id    INT REFERENCES departments(id) ON DELETE SET NULL,
    created_by_id    INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    is_converted     BOOLEAN NOT NULL DEFAULT false,
    converted_task_id INT REFERENCES tasks(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
CREATE TABLE refresh_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(512) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token);
CREATE INDEX idx_refresh_tokens_user  ON refresh_tokens(user_id);
