# DATABASE.md — Data Model
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.1.0  
**Last Updated:** 2026-10-10  
**Database:** PostgreSQL 16

> The authoritative schema is the SQLAlchemy models in `backend/db/models.py` plus the Alembic migrations in `backend/alembic/versions/` (001 to 004). The SQL below is explanatory. `alembic check` (run in CI and by `tests/test_migrations.py`) fails if models and migrations disagree.

---

## 1. Schema Overview

```
┌──────────────┐     ┌──────────────┐     ┌────────────────────┐
│    users     │─────│    tasks     │─────│  task_audit_logs   │
│              │     │              │     │                    │
│  id (PK)     │     │  id (PK)     │     │  id (PK)           │
│  google_id   │     │  title       │     │  task_id (FK)      │
│  email       │     │  description │     │  user_id (FK)      │
│  name        │     │  status      │     │  action            │
│  role        │     │  priority    │     │  changes_json      │
│  google_space│     │  assignee_id │     │  created_at        │
│  prefs_json  │     │  created_by  │─────└────────────────────┘
│  created_at  │─────│  due_date    │
│  updated_at  │     │  completed_at│     ┌────────────────────┐
└──────────────┘     │  deleted_at  │     │ notification_logs  │
                     │  tags        │     │                    │
                     │  created_at  │     │  id (PK)           │
                     │  updated_at  │     │  user_id (FK)      │
                     └──────────────┘     │  type              │
                                          │  message           │
                     ┌──────────────┐     │  sent_at           │
                     │ user_prefs   │     │  status            │
                     │              │     └────────────────────┘
                     │  user_id(FK) │
                     │  key         │
                     │  value       │
                     └──────────────┘
```

---

## 2. Table Definitions

### 2.1 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id       VARCHAR(255) UNIQUE NOT NULL,   -- Google user ID from Chat
    email           VARCHAR(255) UNIQUE NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    role            VARCHAR(50) NOT NULL DEFAULT 'employee',  -- employee|manager|admin
    google_space_id VARCHAR(255),                   -- Primary DM space for proactive msgs
    avatar_url      TEXT,
    timezone        VARCHAR(50) DEFAULT 'Asia/Kolkata',
    is_active       BOOLEAN DEFAULT TRUE,
    last_seen_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_display_name ON users(lower(display_name));
```

**Roles**:
| Role | Permissions |
|------|------------|
| `employee` | Create/update own tasks, assign to self, view own tasks |
| `manager` | All employee + assign tasks to anyone, view team tasks, delete |
| `admin` | All manager + user management, system config |

---

### 2.2 `tasks`

```sql
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'TODO',
                    -- TODO | IN_PROGRESS | REVIEW | DONE | CANCELLED
    priority        VARCHAR(50) NOT NULL DEFAULT 'MEDIUM',
                    -- LOW | MEDIUM | HIGH | CRITICAL
    assignee_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    created_by_id   UUID NOT NULL REFERENCES users(id),
    due_date        DATE,
    completed_at    TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ,     -- Soft delete
    tags            TEXT[] DEFAULT '{}',
    
    -- Full-text search
    search_vector   TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tasks_assignee_id ON tasks(assignee_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_created_by ON tasks(created_by_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_status ON tasks(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_priority ON tasks(priority) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_due_date ON tasks(due_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_tasks_search ON tasks USING GIN(search_vector);
CREATE INDEX idx_tasks_not_deleted ON tasks(id) WHERE deleted_at IS NULL;

-- Composite for common query pattern
CREATE INDEX idx_tasks_assignee_status ON tasks(assignee_id, status) WHERE deleted_at IS NULL;
```

**Status Transitions** (valid state machine):
```
TODO → IN_PROGRESS → REVIEW → DONE
TODO → CANCELLED
IN_PROGRESS → TODO (unstart)
IN_PROGRESS → CANCELLED
REVIEW → IN_PROGRESS (reject)
REVIEW → DONE (approve)
```

---

### 2.3 `task_audit_logs`

```sql
CREATE TABLE task_audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id     UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(50) NOT NULL,
                -- CREATED | UPDATED | DELETED | COMPLETED | ASSIGNED | STATUS_CHANGED
    changes     JSONB,          -- {field: {old: ..., new: ...}}
    source      VARCHAR(50) DEFAULT 'chat',    -- chat | api | scheduler
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for task history queries
CREATE INDEX idx_audit_task_id ON task_audit_logs(task_id, created_at DESC);
CREATE INDEX idx_audit_user_id ON task_audit_logs(user_id, created_at DESC);
```

**Changes JSON Format**:
```json
{
  "status": {"old": "TODO", "new": "IN_PROGRESS"},
  "priority": {"old": "MEDIUM", "new": "HIGH"},
  "assignee_id": {"old": null, "new": "user-uuid"}
}
```

---

### 2.4 `user_preferences`

```sql
CREATE TABLE user_preferences (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key         VARCHAR(100) NOT NULL,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, key)
);

CREATE INDEX idx_user_prefs_user_id ON user_preferences(user_id);
```

**Standard Preference Keys**:
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `daily_briefing` | bool | `true` | Enable daily briefing |
| `briefing_time` | time string | `09:00` | Time for daily briefing |
| `overdue_alert` | bool | `true` | Enable overdue alerts |
| `timezone` | string | `Asia/Kolkata` | User timezone |
| `preferred_view` | string | `kanban` | Dashboard default view |
| `task_limit_in_plan` | int | `5` | Max tasks in daily plan |

---

### 2.5 `notification_logs`

```sql
CREATE TABLE notification_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        VARCHAR(100) NOT NULL,
                -- daily_briefing | overdue_alert | task_assigned | weekly_summary
    message     TEXT NOT NULL,
    google_space_id VARCHAR(255),
    status      VARCHAR(50) DEFAULT 'sent',   -- sent | failed | skipped
    error_msg   TEXT,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_user_id ON notification_logs(user_id, sent_at DESC);
CREATE INDEX idx_notif_type ON notification_logs(type, sent_at DESC);
```

---

### 2.6 `chat_event_ledger`

Idempotency ledger preventing a redelivered Google Chat event (webhook retry)
from double-creating a task or double-executing a confirmed destructive
action. See `backend/crud/chat_events.py` and ARCHITECTURE.md §3.1.

```sql
CREATE TABLE chat_event_ledger (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key     VARCHAR(512) NOT NULL UNIQUE,
    event_type    VARCHAR(50) NOT NULL,     -- MESSAGE | CARD_CLICKED
    status        VARCHAR(20) NOT NULL DEFAULT 'PROCESSING',
                  -- PROCESSING | COMPLETED | FAILED
    response_text TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ
);

CREATE INDEX ix_chat_event_ledger_event_key ON chat_event_ledger(event_key);
```

Migration: `backend/alembic/versions/003_chat_event_ledger.py`. `event_key` is covered by the named unique constraint `uq_chat_event_ledger_event_key`.

---

### 2.7 `agent_execution_traces`

One row per agent request (chat or dashboard), written by `agents/orchestrator.py`. Powers the Agent runs screen. Readable only by the user who made the request.

```sql
CREATE TABLE agent_execution_traces (
    id                UUID PRIMARY KEY,
    request_id        VARCHAR(255) NOT NULL,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thread_id         VARCHAR(255) NOT NULL,
    intent            VARCHAR(50),
    confidence        FLOAT,
    active_agent      VARCHAR(100),
    agents_invoked    JSON NOT NULL,      -- ["supervisor", "task_agent"]
    tool_calls_made   JSON NOT NULL,
    node_durations_ms JSON NOT NULL,      -- {"supervisor": 120.5, ...}
    total_duration_ms FLOAT NOT NULL,
    status            VARCHAR(50) NOT NULL,  -- SUCCESS | NEEDS_CONFIRMATION | TIMEOUT | FAILURE
    error_code        VARCHAR(100),
    error_message     TEXT,
    started_at        TIMESTAMPTZ NOT NULL,
    completed_at      TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL
);
-- indexes: request_id, user_id, thread_id, (user_id, created_at), (thread_id, created_at)
```

### 2.8 Notes that differ from the original design

- `users.hashed_password` is nullable (Google and Chat users have none); `google_id` and `email` are unique.
- `notification_logs.status` is `sent` (API success confirmed), `failed` (attempted, with `error_msg`) or `skipped` (no Google Chat account linked). Jobs never record `sent` without a successful delivery. Types: `daily_briefing`, `overdue_alert`, `weekly_summary`, `task_assigned`, `task_updated`, `task_completed`.
- `user_preferences` boolean keys read by the scheduler: `daily_briefing`, `overdue_alert`, `weekly_summary`. Values `false`, `0`, `off`, `no` (any case) mean opted out.
- `users.google_space_id` is set only from a verified Chat webhook event in a DM space; it cannot be edited through the API.
- Task `tags` is a JSON array (portable across Postgres and the SQLite used in tests), searched with a substring match. Partial indexes and a `tsvector` column from the first design were not implemented; see OPERATIONS.md section 8 if the table grows very large.
- Single-column indexes use the `ix_<table>_<column>` names from the models. Migration 004 aligned the earlier `idx_*` names and dropped three indexes that duplicated unique constraints.

## 3. SQLAlchemy Models

```python
# backend/db/models.py

import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Boolean, Date, DateTime, ForeignKey, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), default="employee")
    google_space_id: Mapped[str | None] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tasks_assigned: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee")
    tasks_created: Mapped[list["Task"]] = relationship("Task", foreign_keys="Task.created_by_id", back_populates="creator")

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="TODO")
    priority: Mapped[str] = mapped_column(String(50), default="MEDIUM")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    assignee: Mapped["User | None"] = relationship("User", foreign_keys=[assignee_id], back_populates="tasks_assigned")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id], back_populates="tasks_created")
    audit_logs: Mapped[list["TaskAuditLog"]] = relationship("TaskAuditLog", back_populates="task")

class TaskAuditLog(Base):
    __tablename__ = "task_audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID, ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    changes: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(50), default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    
    task: Mapped["Task"] = relationship("Task", back_populates="audit_logs")
```

---

## 4. Alembic Migration Strategy

```
backend/
  alembic/
    versions/
      001_create_users.py
      002_create_tasks.py
      003_create_audit_logs.py
      004_create_user_preferences.py
      005_create_notification_logs.py
      006_add_search_indexes.py
    env.py
    alembic.ini
```

Commands:
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## 5. Query Patterns

### Get user tasks (active, sorted)
```python
stmt = select(Task).where(
    Task.assignee_id == user_id,
    Task.status.in_(["TODO", "IN_PROGRESS", "REVIEW"]),
    Task.deleted_at.is_(None)
).order_by(
    case({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}, value=Task.priority),
    Task.due_date.asc().nullslast()
)
```

### Full-text search
```python
stmt = select(Task).where(
    Task.search_vector.op("@@")(func.plainto_tsquery("english", query)),
    Task.deleted_at.is_(None)
).order_by(
    func.ts_rank(Task.search_vector, func.plainto_tsquery("english", query)).desc()
)
```

### Overdue tasks
```python
stmt = select(Task).where(
    Task.due_date < func.current_date(),
    Task.status.not_in(["DONE", "CANCELLED"]),
    Task.deleted_at.is_(None)
).order_by(Task.due_date.asc())
```
