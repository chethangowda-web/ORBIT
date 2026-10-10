"""Add task_attachments for files on tasks.

Revision ID: 006_task_attachments
Revises: 005_task_comments
Create Date: 2026-10-11 09:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_task_attachments"
down_revision: Union[str, None] = "005_task_comments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_name"),
    )
    op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])
    op.create_index("ix_task_attachments_uploaded_by_id", "task_attachments", ["uploaded_by_id"])


def downgrade() -> None:
    op.drop_index("ix_task_attachments_uploaded_by_id", table_name="task_attachments")
    op.drop_index("ix_task_attachments_task_id", table_name="task_attachments")
    op.drop_table("task_attachments")
