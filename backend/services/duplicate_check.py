"""Is this new task already on the list? One check shared by the API, Chat and the AI agent."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from auth.rbac import Role
from crud import tasks as task_crud
from crud import users as user_crud
from services.duplicates import SAME, SIMILAR, find_similar
from services.wording import friendly
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from tools.base import get_tool_session
from db.models import Task, User

MIN_TITLE_LENGTH = 3
CANDIDATE_LIMIT = 300  # most recently updated open tasks the person may see


def task_view(task: Task, score: float) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "title": task.title,
        "status": task.status,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "assignee": task.assignee.display_name if task.assignee else None,
        "score": round(score, 2),
        "same": score >= SAME,
    }


async def similar_open_tasks(db, viewer: User, title: str, limit: int = 3) -> list[tuple[float, Task]]:
    """Open tasks the viewer may see whose title is close to `title`, best match first."""
    if len((title or "").strip()) < MIN_TITLE_LENGTH:
        return []
    stmt = (
        select(Task)
        .options(selectinload(Task.assignee))
        .where(Task.deleted_at.is_(None), Task.status.not_in(["DONE", "CANCELLED"]))
        .order_by(Task.updated_at.desc())
        .limit(CANDIDATE_LIMIT)
    )
    if Role.from_str(viewer.role) == Role.EMPLOYEE:
        stmt = stmt.where(or_(Task.assignee_id == viewer.id, Task.created_by_id == viewer.id))
    rows = list((await db.execute(stmt)).scalars().all())
    return find_similar(title, rows, threshold=SIMILAR, limit=limit)


@dataclass
class DuplicateCheck:
    blocking: Optional[dict[str, Any]] = None  # the very same task, for the same person
    similar: list[dict[str, Any]] = field(default_factory=list)  # close, but not the same


def _same_person(existing: Task, wanted_name: Optional[str], viewer: User) -> bool:
    """Would the new task go to the person who already has the existing one?"""
    owner = existing.assignee
    if not wanted_name:
        return owner is None or owner.id == viewer.id
    if owner is None:
        return False
    wanted, name = wanted_name.strip().lower(), owner.display_name.lower()
    return wanted == name or wanted == name.split(" ")[0] or wanted in (owner.email or "").lower()


async def check_for_duplicates(user_id: str, title: str, assignee_name: Optional[str] = None) -> DuplicateCheck:
    async with get_tool_session() as db:
        try:
            viewer = await user_crud.get_user_by_id(db, uuid.UUID(str(user_id)))
        except ValueError:
            viewer = None
        if viewer is None:
            return DuplicateCheck()
        found = await similar_open_tasks(db, viewer, title)
        result = DuplicateCheck()
        for score, task in found:
            if result.blocking is None and score >= SAME and _same_person(task, assignee_name, viewer):
                result.blocking = task_view(task, score)
            else:
                result.similar.append(task_view(task, score))
        return result


def describe(view: dict[str, Any]) -> str:
    """"*Send contract* (in progress, with Rahul, due 2026-10-14)" for a message."""
    bits = [friendly(view.get("status")).lower()]
    bits.append(f"with {view['assignee']}" if view.get("assignee") else "not assigned")
    if view.get("due_date"):
        bits.append(f"due {view['due_date']}")
    return f"*{view['title']}* ({', '.join(bits)})"
