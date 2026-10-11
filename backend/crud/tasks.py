"""
Task CRUD Layer
Database access operations for Task entities, state transitions, and analytics.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import String, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.audit import log_task_action
from db.base import local_today, utc_now
from db.models import Task, TaskAuditLog, User
from exceptions import EntityNotFoundException, OrbitException
from schemas.analytics import DailyCount, TaskStatsResponse, TeamMemberWorkload
from schemas.task import TaskCreate, TaskPriority, TaskStatus, TaskUpdate
from services.notifications import notify_task_event


SORTABLE_COLUMNS = {
    "due_date": Task.due_date,
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "priority": Task.priority,
    "status": Task.status,
    "title": Task.title,
}

CLOSED_STATUSES = ("DONE", "CANCELLED")
LIKE_ESCAPE = "\\"


def case_when(condition):
    """1 when the condition holds else 0, for conditional aggregation."""
    return case((condition, 1), else_=0)


def _like_pattern(raw: str) -> str:
    """Build a case-insensitive contains pattern with LIKE wildcards escaped."""
    cleaned = raw.strip().lower()
    cleaned = cleaned.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
    cleaned = cleaned.replace("%", LIKE_ESCAPE + "%").replace("_", LIKE_ESCAPE + "_")
    return f"%{cleaned}%"


async def _get_actor_name(db: AsyncSession, user_id: Optional[uuid.UUID]) -> str:
    """Resolve a display name for the acting user, used in notification text."""
    if not user_id:
        return "ORBIT"
    result = await db.execute(select(User.display_name).where(User.id == user_id))
    name = result.scalar_one_or_none()
    return name or "A teammate"


def enrich_task_metadata(task: Task) -> Task:
    """Compute virtual properties like days_overdue on a Task model."""
    if task.due_date and task.status not in ["DONE", "CANCELLED"]:
        today = local_today()
        if task.due_date < today:
            setattr(task, "days_overdue", (today - task.due_date).days)
        else:
            setattr(task, "days_overdue", 0)
    else:
        setattr(task, "days_overdue", None)
    return task


async def ensure_assignable_user(db: AsyncSession, user_id: Optional[uuid.UUID]) -> None:
    """A task can only be assigned to an existing, active user. Without this the database raised a
    foreign-key error (HTTP 500), and a bulk assignment aborted halfway."""
    if user_id is None:
        return
    found = (
        await db.execute(select(User.id).where(User.id == user_id, User.is_active.is_(True)))
    ).scalar_one_or_none()
    if found is None:
        raise EntityNotFoundException("User", user_id)


async def create_task(
    db: AsyncSession,
    task_in: TaskCreate,
    created_by_id: uuid.UUID,
    source: str = "api",
) -> Task:
    """Create a new task and record creation in the audit log."""
    await ensure_assignable_user(db, task_in.assignee_id)
    task = Task(
        title=task_in.title.strip(),
        description=task_in.description,
        priority=task_in.priority.value if hasattr(task_in.priority, "value") else task_in.priority,
        status=TaskStatus.TODO.value,
        assignee_id=task_in.assignee_id,
        created_by_id=created_by_id,
        due_date=task_in.due_date,
        tags=task_in.tags or [],
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Record audit log
    await log_task_action(
        db=db,
        task_id=task.id,
        user_id=created_by_id,
        action="CREATED",
        changes={
            "status": {"new": task.status},
            "priority": {"new": task.priority},
            "assignee_id": {"new": str(task.assignee_id) if task.assignee_id else None},
        },
        source=source,
    )
    await db.commit()
    reloaded = await get_task(db, task.id)
    final_task = reloaded if reloaded is not None else enrich_task_metadata(task)

    if final_task.assignee_id and final_task.assignee_id != created_by_id:
        actor_name = await _get_actor_name(db, created_by_id)
        await notify_task_event(
            session=db,
            task=final_task,
            event_type="task_assigned",
            recipient=final_task.assignee,
            actor_name=actor_name,
        )

    return final_task


async def get_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    include_deleted: bool = False,
) -> Optional[Task]:
    """Retrieve single task by ID with relationships."""
    stmt = (
        select(Task)
        .options(
            selectinload(Task.assignee),
            selectinload(Task.creator),
            selectinload(Task.audit_logs).selectinload(TaskAuditLog.user),
        )
        .where(Task.id == task_id)
    )
    if not include_deleted:
        stmt = stmt.where(Task.deleted_at.is_(None))

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if task:
        return enrich_task_metadata(task)
    return None


async def update_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    user_id: Optional[uuid.UUID] = None,
    source: str = "api",
) -> Task:
    """Update task fields and log changed attributes in audit trail."""
    task = await get_task(db, task_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)

    update_dict = task_update.model_dump(exclude_unset=True)
    if update_dict.get("assignee_id") is not None:
        await ensure_assignable_user(db, update_dict["assignee_id"])
    changes = {}

    for field, new_val in update_dict.items():
        if hasattr(new_val, "value"):
            new_val = new_val.value
        old_val = getattr(task, field)
        if old_val != new_val:
            changes[field] = {
                "old": str(old_val) if isinstance(old_val, (uuid.UUID, date, datetime)) else old_val,
                "new": str(new_val) if isinstance(new_val, (uuid.UUID, date, datetime)) else new_val,
            }
            setattr(task, field, new_val)

    if "status" in changes:
        if task.status == TaskStatus.DONE.value and not task.completed_at:
            task.completed_at = utc_now()
        elif task.status != TaskStatus.DONE.value and task.completed_at:
            task.completed_at = None
            changes["completed_at"] = {"old": "set", "new": None}

    if "assignee_id" in changes:
        # Setting the FK column directly does not refresh the `assignee`
        # relationship on this already-identity-mapped instance; without
        # expiring it, a subsequent reload would keep serving the stale
        # (pre-reassignment) related object instead of the new assignee.
        db.expire(task, ["assignee"])

    if changes:
        action_type = "STATUS_CHANGED" if "status" in changes else "UPDATED"
        await log_task_action(
            db=db,
            task_id=task.id,
            user_id=user_id,
            action=action_type,
            changes=changes,
            source=source,
        )

    await db.commit()
    reloaded = await get_task(db, task.id)
    final_task = reloaded if reloaded is not None else enrich_task_metadata(task)

    if changes and final_task.assignee_id and final_task.assignee_id != user_id:
        actor_name = await _get_actor_name(db, user_id)
        event_type = "task_assigned" if "assignee_id" in changes else "task_updated"
        await notify_task_event(
            session=db,
            task=final_task,
            event_type=event_type,
            recipient=final_task.assignee,
            actor_name=actor_name,
        )

    return final_task


async def soft_delete_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    source: str = "api",
) -> Task:
    """Mark a task as soft-deleted."""
    task = await get_task(db, task_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)

    task.deleted_at = utc_now()
    await log_task_action(
        db=db,
        task_id=task.id,
        user_id=user_id,
        action="DELETED",
        changes={"deleted_at": {"new": str(task.deleted_at)}},
        source=source,
    )
    await db.commit()
    return task


async def complete_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    completion_note: Optional[str] = None,
    source: str = "api",
) -> Task:
    """Transition a task to DONE state and record completion."""
    task = await get_task(db, task_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)

    if task.status == TaskStatus.DONE.value:
        return task
    if task.status == TaskStatus.CANCELLED.value:
        raise OrbitException(
            "Cancelled tasks cannot be completed. Reopen the task first.",
            status_code=409,
        )

    old_status = task.status
    task.status = TaskStatus.DONE.value
    task.completed_at = utc_now()

    changes = {
        "status": {"old": old_status, "new": TaskStatus.DONE.value},
        "completed_at": {"new": str(task.completed_at)},
    }
    if completion_note:
        changes["completion_note"] = {"new": completion_note}

    await log_task_action(
        db=db,
        task_id=task.id,
        user_id=user_id,
        action="COMPLETED",
        changes=changes,
        source=source,
    )
    await db.commit()
    reloaded = await get_task(db, task.id)
    final_task = reloaded if reloaded is not None else enrich_task_metadata(task)

    if final_task.created_by_id and final_task.created_by_id != user_id:
        actor_name = await _get_actor_name(db, user_id)
        await notify_task_event(
            session=db,
            task=final_task,
            event_type="task_completed",
            recipient=final_task.creator,
            actor_name=actor_name,
        )

    return final_task


async def list_tasks(
    db: AsyncSession,
    status: Optional[List[str]] = None,
    priority: Optional[List[str]] = None,
    assignee_id: Optional[uuid.UUID] = None,
    created_by_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    q: Optional[str] = None,
    include_completed: bool = True,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "due_date",
    sort_dir: str = "asc",
) -> Tuple[List[Task], int]:
    """Search and paginate tasks with dynamic filtering."""
    stmt = (
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.creator))
        .where(Task.deleted_at.is_(None))
    )

    if status:
        stmt = stmt.where(Task.status.in_(status))
    elif not include_completed:
        stmt = stmt.where(Task.status.not_in(["DONE", "CANCELLED"]))

    if priority:
        stmt = stmt.where(Task.priority.in_(priority))
    if user_id:
        stmt = stmt.where(or_(Task.assignee_id == user_id, Task.created_by_id == user_id))
    else:
        if assignee_id:
            stmt = stmt.where(Task.assignee_id == assignee_id)
        if created_by_id:
            stmt = stmt.where(Task.created_by_id == created_by_id)
    if due_before:
        stmt = stmt.where(Task.due_date <= due_before)
    if due_after:
        stmt = stmt.where(Task.due_date >= due_after)
    if q and q.strip():
        pattern = _like_pattern(q)
        stmt = stmt.where(
            or_(
                func.lower(Task.title).like(pattern, escape=LIKE_ESCAPE),
                func.lower(func.coalesce(Task.description, "")).like(pattern, escape=LIKE_ESCAPE),
                func.lower(cast(Task.tags, String)).like(pattern, escape=LIKE_ESCAPE),
            )
        )

    # Count total matching
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Sorting
    sort_col = SORTABLE_COLUMNS.get(sort_by, Task.due_date)
    if sort_dir.lower() == "desc":
        stmt = stmt.order_by(sort_col.desc().nullslast(), Task.id)
    else:
        stmt = stmt.order_by(sort_col.asc().nullslast(), Task.id)

    # Pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    result = await db.execute(stmt)
    tasks = [enrich_task_metadata(t) for t in result.scalars().all()]
    return tasks, total_count


async def get_overdue_tasks(
    db: AsyncSession, user_id: Optional[uuid.UUID] = None
) -> List[Task]:
    """Return all incomplete tasks whose due date has passed."""
    today = local_today()
    stmt = (
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.creator))
        .where(
            Task.deleted_at.is_(None),
            Task.status.not_in(["DONE", "CANCELLED"]),
            Task.due_date < today,
        )
    )
    if user_id:
        stmt = stmt.where(or_(Task.assignee_id == user_id, Task.created_by_id == user_id))

    stmt = stmt.order_by(Task.due_date.asc())
    result = await db.execute(stmt)
    return [enrich_task_metadata(t) for t in result.scalars().all()]


async def get_tasks_due_today(
    db: AsyncSession, user_id: Optional[uuid.UUID] = None
) -> List[Task]:
    """Return all incomplete tasks due today."""
    today = local_today()
    stmt = (
        select(Task)
        .options(selectinload(Task.assignee), selectinload(Task.creator))
        .where(
            Task.deleted_at.is_(None),
            Task.status.not_in(["DONE", "CANCELLED"]),
            Task.due_date == today,
        )
    )
    if user_id:
        stmt = stmt.where(Task.assignee_id == user_id)

    result = await db.execute(stmt)
    return [enrich_task_metadata(t) for t in result.scalars().all()]


async def get_task_stats(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    involved_user_id: Optional[uuid.UUID] = None,
    trend_days: int = 14,
) -> TaskStatsResponse:
    """Aggregate task metrics computed in SQL.

    ``user_id`` limits to tasks assigned to that user; ``involved_user_id``
    limits to tasks assigned to or created by them (the employee visibility
    scope used by the task list). Every figure comes from the database.
    """
    scope = [Task.deleted_at.is_(None)]
    if user_id:
        scope.append(Task.assignee_id == user_id)
    if involved_user_id:
        scope.append(or_(Task.assignee_id == involved_user_id, Task.created_by_id == involved_user_id))
    if date_from:
        scope.append(Task.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        scope.append(Task.created_at <= datetime.combine(date_to, datetime.max.time()))

    status_rows = await db.execute(select(Task.status, func.count()).where(*scope).group_by(Task.status))
    priority_rows = await db.execute(select(Task.priority, func.count()).where(*scope).group_by(Task.priority))
    statuses = {"TODO": 0, "IN_PROGRESS": 0, "REVIEW": 0, "DONE": 0, "CANCELLED": 0}
    priorities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    statuses.update({k: v for k, v in status_rows.all() if k in statuses})
    priorities.update({k: v for k, v in priority_rows.all() if k in priorities})

    total = sum(statuses.values())
    completed = statuses["DONE"]
    overdue = (
        await db.execute(
            select(func.count()).where(
                *scope,
                Task.due_date < local_today(),
                Task.status.not_in(CLOSED_STATUSES),
            )
        )
    ).scalar_one()

    durations = await db.execute(
        select(Task.created_at, Task.completed_at).where(
            *scope, Task.status == "DONE", Task.completed_at.is_not(None)
        )
    )
    spans = [
        (done - created).total_seconds() / 86400
        for created, done in durations.all()
        if created and done
    ]
    avg_days = round(sum(spans) / len(spans), 1) if spans else 0.0

    since = local_today() - timedelta(days=trend_days - 1)
    created_rows = await db.execute(
        select(func.date(Task.created_at), func.count())
        .where(*scope, Task.created_at >= datetime.combine(since, datetime.min.time()))
        .group_by(func.date(Task.created_at))
    )
    by_day = {str(day): count for day, count in created_rows.all()}
    per_day = [
        DailyCount(
            date=str(since + timedelta(days=i)),
            count=by_day.get(str(since + timedelta(days=i)), 0),
        )
        for i in range(trend_days)
    ]

    return TaskStatsResponse(
        total_tasks=total,
        completed_tasks=completed,
        in_progress_tasks=statuses["IN_PROGRESS"],
        overdue_tasks=overdue,
        completion_rate=round(completed / total, 2) if total else 0.0,
        avg_completion_days=avg_days,
        tasks_by_priority=priorities,
        tasks_by_status=statuses,
        by_priority=priorities,
        by_status=statuses,
        tasks_created_per_day=per_day,
    )


async def get_team_workload(db: AsyncSession) -> List[TeamMemberWorkload]:
    """Per-member workload from a single grouped query (no per-user round trips)."""
    today = local_today()
    open_overdue = (Task.due_date < today) & Task.status.not_in(CLOSED_STATUSES)
    stmt = (
        select(
            User.id,
            User.display_name,
            User.email,
            User.role,
            func.count(Task.id),
            func.coalesce(func.sum(case_when(Task.status == "DONE")), 0),
            func.coalesce(func.sum(case_when(open_overdue)), 0),
            func.coalesce(func.sum(case_when(Task.priority.in_(["HIGH", "CRITICAL"]))), 0),
        )
        .select_from(User)
        .outerjoin(Task, (Task.assignee_id == User.id) & Task.deleted_at.is_(None))
        .where(User.is_active.is_(True))
        .group_by(User.id, User.display_name, User.email, User.role)
        .order_by(User.display_name)
    )
    rows = (await db.execute(stmt)).all()
    return [
        TeamMemberWorkload(
            user_id=str(uid),
            display_name=name,
            email=email,
            role=role,
            assigned_tasks=total,
            completed_tasks=int(done),
            overdue_tasks=int(late),
            high_priority_tasks=int(high),
            completion_rate=round(int(done) / total, 2) if total else 0.0,
        )
        for uid, name, email, role, total, done, late, high in rows
    ]
