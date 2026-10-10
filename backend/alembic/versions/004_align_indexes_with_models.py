"""Align indexes with the ORM models and drop redundant duplicates.

Migrations 001 and 003 created ``idx_*`` indexes (and extra indexes on columns that
already carry a unique constraint) while the models declare ``ix_*`` indexes, so
``alembic check`` always reported drift. This migration is index-only: no table or
data changes.

* ``users.email`` / ``users.google_id`` / ``chat_event_ledger.event_key`` are already
  covered by unique constraints, so the duplicate plain indexes are dropped.
* Remaining ``idx_*`` single-column indexes are recreated under the ``ix_*`` names
  the models use.

Revision ID: 004_align_indexes
Revises: 003_chat_event_ledger
Create Date: 2026-10-10 18:00:00.000000
"""

from typing import Sequence, Union
from alembic import op

revision: str = "004_align_indexes"
down_revision: Union[str, None] = "003_chat_event_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old name, new name, table, columns)
RENAMED = [
    ("idx_tasks_status", "ix_tasks_status", "tasks", ["status"]),
    ("idx_tasks_priority", "ix_tasks_priority", "tasks", ["priority"]),
    ("idx_tasks_assignee_id", "ix_tasks_assignee_id", "tasks", ["assignee_id"]),
    ("idx_tasks_created_by_id", "ix_tasks_created_by_id", "tasks", ["created_by_id"]),
    ("idx_tasks_due_date", "ix_tasks_due_date", "tasks", ["due_date"]),
    ("idx_tasks_deleted_at", "ix_tasks_deleted_at", "tasks", ["deleted_at"]),
    ("idx_audit_task_id", "ix_task_audit_logs_task_id", "task_audit_logs", ["task_id"]),
    ("idx_audit_user_id", "ix_task_audit_logs_user_id", "task_audit_logs", ["user_id"]),
    ("idx_user_prefs_user_id", "ix_user_preferences_user_id", "user_preferences", ["user_id"]),
    ("idx_notif_user_id", "ix_notification_logs_user_id", "notification_logs", ["user_id"]),
    ("idx_notif_type", "ix_notification_logs_type", "notification_logs", ["type"]),
]

# (name, table, columns) redundant with an existing unique constraint
REDUNDANT = [
    ("idx_users_email", "users", ["email"]),
    ("idx_users_google_id", "users", ["google_id"]),
    ("ix_chat_event_ledger_event_key", "chat_event_ledger", ["event_key"]),
]


def upgrade() -> None:
    for old, new, table, cols in RENAMED:
        op.drop_index(old, table_name=table)
        op.create_index(new, table, cols)
    for name, table, _cols in REDUNDANT:
        op.drop_index(name, table_name=table)
    # Index the column the notification dedupe query filters on.
    op.create_index("ix_notification_logs_sent_at", "notification_logs", ["sent_at"])


def downgrade() -> None:
    op.drop_index("ix_notification_logs_sent_at", table_name="notification_logs")
    for name, table, cols in REDUNDANT:
        op.create_index(name, table, cols)
    for old, new, table, cols in RENAMED:
        op.drop_index(new, table_name=table)
        op.create_index(old, table, cols)
