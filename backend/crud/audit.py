"""
Audit Logging CRUD Layer
Captures immutable audit trail records for task mutations.
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import TaskAuditLog


async def log_task_action(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: Optional[uuid.UUID],
    action: str,
    changes: Optional[Dict[str, Any]] = None,
    source: str = "api",
) -> TaskAuditLog:
    """Create an audit log record for a task action."""
    audit_entry = TaskAuditLog(
        task_id=task_id,
        user_id=user_id,
        action=action,
        changes=changes,
        source=source,
    )
    db.add(audit_entry)
    await db.flush()
    return audit_entry


async def get_task_audit_history(
    db: AsyncSession, task_id: uuid.UUID
) -> List[TaskAuditLog]:
    """Retrieve full chronological audit history for a task."""
    from sqlalchemy.orm import selectinload  # avoid circular import
    stmt = (
        select(TaskAuditLog)
        .options(selectinload(TaskAuditLog.user))
        .where(TaskAuditLog.task_id == task_id)
        .order_by(TaskAuditLog.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
