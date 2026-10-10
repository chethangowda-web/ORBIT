"""Task attachment queries."""

import uuid
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.audit import log_task_action
from db.models import Task, TaskAttachment, User


async def list_attachments(db: AsyncSession, task_id: uuid.UUID) -> List[TaskAttachment]:
    stmt = (
        select(TaskAttachment)
        .options(selectinload(TaskAttachment.uploader))
        .where(TaskAttachment.task_id == task_id)
        .order_by(TaskAttachment.created_at.asc(), TaskAttachment.id)
    )
    return list((await db.execute(stmt)).scalars().all())


async def count_attachments(db: AsyncSession, task_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(TaskAttachment).where(TaskAttachment.task_id == task_id)
    return (await db.execute(stmt)).scalar_one()


async def get_attachment(db: AsyncSession, task_id: uuid.UUID, attachment_id: uuid.UUID) -> Optional[TaskAttachment]:
    stmt = (
        select(TaskAttachment)
        .options(selectinload(TaskAttachment.uploader))
        .where(TaskAttachment.id == attachment_id, TaskAttachment.task_id == task_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def add_attachment(
    db: AsyncSession,
    task: Task,
    uploader: User,
    filename: str,
    stored_name: str,
    content_type: str,
    size_bytes: int,
) -> TaskAttachment:
    attachment = TaskAttachment(
        task_id=task.id,
        uploaded_by_id=uploader.id,
        filename=filename,
        stored_name=stored_name,
        content_type=content_type,
        size_bytes=size_bytes,
    )
    db.add(attachment)
    await log_task_action(
        db=db,
        task_id=task.id,
        user_id=uploader.id,
        action="ATTACHED",
        changes={"attachment": {"new": filename}},
        source="api",
    )
    await db.commit()
    created = await get_attachment(db, task.id, attachment.id)
    return created if created is not None else attachment


async def delete_attachment(db: AsyncSession, attachment: TaskAttachment, actor: User) -> None:
    await log_task_action(
        db=db,
        task_id=attachment.task_id,
        user_id=actor.id,
        action="ATTACHMENT_REMOVED",
        changes={"attachment": {"old": attachment.filename}},
        source="api",
    )
    await db.delete(attachment)
    await db.commit()
