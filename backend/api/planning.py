"""Planning endpoints: your week, and who has room for more work."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import local_today
from db.models import Task, User
from db.session import get_db
from dependencies import get_current_user, require_role
from schemas.common import api_response
from services.assignment import rank_assignees
from services.week_plan import build_week_plan

router = APIRouter(prefix="/planning", tags=["Planning"])

OPEN_STATUSES = ["TODO", "IN_PROGRESS", "REVIEW"]
MAX_TASKS_PLANNED = 300


@router.get("/week")
async def my_week(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Your open tasks arranged over the next five working days: late work first, then the soonest
    deadlines, with tight spots flagged. Only your own tasks are used."""
    rows = (
        await db.execute(
            select(Task)
            .where(Task.assignee_id == current_user.id, Task.deleted_at.is_(None), Task.status.in_(OPEN_STATUSES))
            .limit(MAX_TASKS_PLANNED)
        )
    ).scalars().all()
    tasks = [
        {"id": str(t.id), "title": t.title, "priority": t.priority, "status": t.status, "due_date": t.due_date}
        for t in rows
    ]
    return api_response(data=build_week_plan(tasks, local_today()).to_dict())


@router.get("/suggest-assignee")
async def suggest_assignee(
    limit: int = 3,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
) -> Dict[str, Any]:
    """The people with the most room, least busy first, each with a plain reason. Managers and admins only."""
    candidates = await rank_assignees(db, limit=max(1, min(limit, 10)))
    return api_response(data=[c.to_dict() for c in candidates])
