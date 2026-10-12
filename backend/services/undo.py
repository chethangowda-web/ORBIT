"""Undo the last thing ORBIT did for someone in chat.

Every change is already in the task audit trail with its old and new values, so undoing is replaying that
trail backwards. This is plain code, not a prompt: predictable, instant, and it spends no AI request.

What counts as "the last thing": the person's most recent run of chat changes, meaning edits that are close
together in time (a multi-step request makes several), and no older than 30 minutes. A change is only
reverted if the task still has the value ORBIT gave it, so someone else's later edit is never overwritten.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select

from crud import tasks as task_crud
from db.base import utc_now
from db.models import Task, TaskAuditLog
from schemas.task import TaskPriority, TaskStatus, TaskUpdate
from tools.base import get_tool_session

WINDOW = timedelta(minutes=30)
SAME_RUN_GAP = timedelta(seconds=15)
SOURCES = ("chat", "undo")
REVERTABLE = ("title", "description", "status", "priority", "assignee_id", "due_date", "tags")
MAX_ROWS = 60


@dataclass
class UndoResult:
    reverted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    nothing_to_undo: Optional[str] = None


def _same(current: Any, logged: Any) -> bool:
    return (None if current is None else str(current)) == (None if logged is None else str(logged))


def _typed(field_name: str, value: Any) -> Any:
    """The logged (string) value, converted back to what TaskUpdate expects."""
    if value is None:
        return None
    if field_name == "assignee_id":
        return uuid.UUID(str(value))
    if field_name == "due_date":
        return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    if field_name == "status":
        return TaskStatus(str(value).split(".")[-1])
    if field_name == "priority":
        return TaskPriority(str(value).split(".")[-1])
    return value


async def _latest_run(db, user_id: uuid.UUID) -> list[TaskAuditLog]:
    rows = (
        await db.execute(
            select(TaskAuditLog)
            .where(
                TaskAuditLog.user_id == user_id,
                TaskAuditLog.source.in_(SOURCES),
                TaskAuditLog.created_at >= utc_now() - WINDOW,
            )
            .order_by(TaskAuditLog.created_at.desc())
            .limit(MAX_ROWS)
        )
    ).scalars().all()
    run: list[TaskAuditLog] = []
    previous: Optional[datetime] = None
    for row in rows:
        if previous is not None and previous - row.created_at > SAME_RUN_GAP:
            break
        run.append(row)
        previous = row.created_at
    return run


async def _title(db, task_id: uuid.UUID) -> str:
    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    return task.title if task else "a task"


async def undo_last_changes(user_id: str) -> UndoResult:
    uid = uuid.UUID(str(user_id))
    result = UndoResult()
    async with get_tool_session() as db:
        run = await _latest_run(db, uid)
        if not run:
            result.nothing_to_undo = "There is nothing recent to undo. I can only undo changes made through chat in the last 30 minutes."
            return result
        if run[0].source == "undo":
            result.nothing_to_undo = "Your last change has already been undone."
            return result

        for entry in run:  # newest first, so a task edited twice unwinds in the right order
            task = (await db.execute(select(Task).where(Task.id == entry.task_id))).scalar_one_or_none()
            name = task.title if task else await _title(db, entry.task_id)
            changes = entry.changes or {}
            try:
                if task is None:
                    result.skipped.append(f"*{name}* no longer exists")
                elif entry.action == "CREATED":
                    if task.deleted_at is not None:
                        continue
                    await task_crud.soft_delete_task(db, task.id, user_id=uid, source="undo")
                    result.reverted.append(f"Removed *{name}*, which had just been created")
                elif entry.action == "DELETED":
                    if task.deleted_at is None:
                        continue
                    task.deleted_at = None
                    await task_crud.log_task_action(
                        db=db, task_id=task.id, user_id=uid, action="UPDATED",
                        changes={"deleted_at": {"old": "deleted", "new": None}}, source="undo",
                    )
                    await db.commit()
                    result.reverted.append(f"Brought back *{name}*")
                else:
                    revert: dict[str, Any] = {}
                    stale = False
                    for key in REVERTABLE:
                        change = changes.get(key)
                        if not isinstance(change, dict) or "old" not in change:
                            continue
                        if not _same(getattr(task, key), change.get("new")):
                            stale = True
                            break
                        revert[key] = _typed(key, change["old"])
                    if stale:
                        result.skipped.append(f"*{name}* was changed again since, so I left it alone")
                    elif revert:
                        await task_crud.update_task(db, task.id, TaskUpdate(**revert), user_id=uid, source="undo")
                        result.reverted.append(f"Put *{name}* back as it was")
            except Exception:
                await db.rollback()
                result.skipped.append(f"I could not undo the change to *{name}*")
    return result


def format_undo(result: UndoResult) -> str:
    if result.nothing_to_undo:
        return result.nothing_to_undo
    lines: list[str] = []
    if result.reverted:
        lines.append("↩️ *Undone*")
        lines += [f"• {line}" for line in result.reverted]
    if result.skipped:
        lines.append("\n*Not undone*" if result.reverted else "*Nothing was undone*")
        lines += [f"• {line}" for line in result.skipped]
    return "\n".join(lines) or "There was nothing to undo."
