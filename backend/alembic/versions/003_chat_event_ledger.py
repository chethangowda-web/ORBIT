"""Create chat_event_ledger table for Google Chat webhook idempotency

Revision ID: 003_chat_event_ledger
Revises: 002_agent_execution_traces
Create Date: 2026-10-10 10:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_chat_event_ledger"
down_revision: Union[str, None] = "002_agent_execution_traces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_event_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=512), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PROCESSING"),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_chat_event_ledger_event_key"),
    )
    op.create_index("ix_chat_event_ledger_event_key", "chat_event_ledger", ["event_key"])


def downgrade() -> None:
    op.drop_index("ix_chat_event_ledger_event_key", table_name="chat_event_ledger")
    op.drop_table("chat_event_ledger")
