"""Who has room for more work? Powers "who should take this?", the form's Suggest button and the AI agent.

The ranking is plain arithmetic on real task counts, so it is explainable ("2 open tasks, none late")
and needs no AI.
"""

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import local_today
from db.models import Task, User

# Roles that do the work. Admin accounts administer the system and are not suggested.
WORKER_ROLES = ("employee", "manager")


def score_of(open_tasks: int, overdue: int, high: int) -> int:
    """Higher means busier. Late work counts double: that person is already behind."""
    return open_tasks + 2 * overdue + high


def _reason(open_tasks: int, overdue: int) -> str:
    if open_tasks == 0:
        return "no open tasks"
    noun = "task" if open_tasks == 1 else "tasks"
    return f"{open_tasks} open {noun}, {'none late' if overdue == 0 else f'{overdue} late'}"


@dataclass(frozen=True)
class Candidate:
    user_id: str
    name: str
    role: str
    open_tasks: int
    overdue_tasks: int
    high_priority_tasks: int
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.name,
            "role": self.role,
            "open_tasks": self.open_tasks,
            "overdue_tasks": self.overdue_tasks,
            "reason": self.reason,
        }


def rank_loads(rows: list[dict[str, Any]], limit: Optional[int] = None) -> list[Candidate]:
    """Least busy first. Ties: fewer late tasks, then name."""
    candidates = [
        Candidate(
            user_id=str(r["user_id"]),
            name=r["name"],
            role=r["role"],
            open_tasks=r["open_tasks"],
            overdue_tasks=r["overdue_tasks"],
            high_priority_tasks=r["high_priority_tasks"],
            score=score_of(r["open_tasks"], r["overdue_tasks"], r["high_priority_tasks"]),
            reason=_reason(r["open_tasks"], r["overdue_tasks"]),
        )
        for r in rows
        if r.get("role") in WORKER_ROLES
    ]
    candidates.sort(key=lambda c: (c.score, c.overdue_tasks, c.name.lower()))
    return candidates[:limit] if limit else candidates


async def load_rows(db: AsyncSession) -> list[dict[str, Any]]:
    """Open-task counts for every active worker (people with no open tasks included)."""
    users = (await db.execute(select(User).where(User.is_active.is_(True), User.role.in_(WORKER_ROLES)))).scalars().all()
    today = local_today()
    counts = await db.execute(
        select(
            Task.assignee_id,
            func.count(Task.id),
            func.coalesce(func.sum(case((Task.due_date < today, 1), else_=0)), 0),
            func.coalesce(func.sum(case((Task.priority.in_(["HIGH", "CRITICAL"]), 1), else_=0)), 0),
        )
        .where(Task.deleted_at.is_(None), Task.status.not_in(["DONE", "CANCELLED"]), Task.assignee_id.is_not(None))
        .group_by(Task.assignee_id)
    )
    by_user = {row[0]: (int(row[1]), int(row[2]), int(row[3])) for row in counts.all()}
    rows = []
    for user in users:
        open_tasks, overdue, high = by_user.get(user.id, (0, 0, 0))
        rows.append(
            {
                "user_id": user.id,
                "name": user.display_name,
                "role": user.role,
                "open_tasks": open_tasks,
                "overdue_tasks": overdue,
                "high_priority_tasks": high,
            }
        )
    return rows


async def rank_assignees(db: AsyncSession, limit: int = 3) -> list[Candidate]:
    return rank_loads(await load_rows(db), limit=limit)
