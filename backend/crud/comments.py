"""Task comment queries."""

import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.audit import log_task_action
from db.models import Task, TaskComment, User


async def list_comments(db: AsyncSession, task_id: uuid.UUID) -> List[TaskComment]:
    """Oldest first, so the thread reads top to bottom."""
    stmt = (
        select(TaskComment)
        .options(selectinload(TaskComment.author))
        .where(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc(), TaskComment.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_comment(db: AsyncSession, task_id: uuid.UUID, comment_id: uuid.UUID) -> Optional[TaskComment]:
    stmt = (
        select(TaskComment)
        .options(selectinload(TaskComment.author))
        .where(TaskComment.id == comment_id, TaskComment.task_id == task_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_comment(db: AsyncSession, task: Task, author: User, body: str, source: str = "api") -> TaskComment:
    """Store a comment and record it in the task's audit trail."""
    comment = TaskComment(task_id=task.id, author_id=author.id, body=body)
    db.add(comment)
    excerpt = body if len(body) <= 120 else body[:117] + "..."
    await log_task_action(
        db=db,
        task_id=task.id,
        user_id=author.id,
        action="COMMENTED",
        changes={"comment": {"new": excerpt}},
        source=source,
    )
    await db.commit()
    created = await get_comment(db, task.id, comment.id)
    return created if created is not None else comment


async def delete_comment(db: AsyncSession, comment: TaskComment) -> None:
    await db.delete(comment)
    await db.commit()
