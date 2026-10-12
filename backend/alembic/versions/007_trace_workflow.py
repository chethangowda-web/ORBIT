"""Record how each agent run was classified and its ordered workflow steps.

Revision ID: 007_trace_workflow
Revises: 006_task_attachments
Create Date: 2026-10-12 10:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_trace_workflow"
down_revision: Union[str, None] = "006_task_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_execution_traces", sa.Column("classifier", sa.String(length=20), nullable=True))
    op.add_column("agent_execution_traces", sa.Column("steps", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_execution_traces", "steps")
    op.drop_column("agent_execution_traces", "classifier")
