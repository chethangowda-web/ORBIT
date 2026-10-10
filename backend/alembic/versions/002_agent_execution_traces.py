"""Create agent_execution_traces table

Revision ID: 002_agent_execution_traces
Revises: 001_initial_schema
Create Date: 2026-10-10 09:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_agent_execution_traces"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_traces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("active_agent", sa.String(length=100), nullable=True),
        sa.Column("agents_invoked", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tool_calls_made", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("node_durations_ms", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("total_duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="SUCCESS"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_execution_traces_request_id", "agent_execution_traces", ["request_id"])
    op.create_index("ix_agent_execution_traces_user_id", "agent_execution_traces", ["user_id"])
    op.create_index("ix_agent_execution_traces_thread_id", "agent_execution_traces", ["thread_id"])
    op.create_index("idx_traces_user_created", "agent_execution_traces", ["user_id", "created_at"])
    op.create_index("idx_traces_thread_created", "agent_execution_traces", ["thread_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_traces_thread_created", table_name="agent_execution_traces")
    op.drop_index("idx_traces_user_created", table_name="agent_execution_traces")
    op.drop_index("ix_agent_execution_traces_thread_id", table_name="agent_execution_traces")
    op.drop_index("ix_agent_execution_traces_user_id", table_name="agent_execution_traces")
    op.drop_index("ix_agent_execution_traces_request_id", table_name="agent_execution_traces")
    op.drop_table("agent_execution_traces")
