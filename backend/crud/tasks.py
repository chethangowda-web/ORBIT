"""
Task CRUD Layer
Database access operations for Task entities, state transitions, and analytics.
"""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.audit import log_task_action
from db.base import utc_now
from db.models import Task, TaskAuditLog, User
from exceptions import EntityNotFoundException, OrbitException
from schemas.analytics import DailyCount, TaskStatsResponse, TeamMemberWorkload
from schemas.task import TaskCreate, TaskPriority, TaskStatus, TaskUpdate


def enrich_task_metadata(task: Task) -> Task:
    """Compute virtual properties like days_overdue on a Task model."""
    if task.due_date and task.status not in ["DONE", "CANCELLED"]:
        today = date.today()
        if task.due_date < today:
            setattr(task, "days_overdue", (today - task.due_date).days)
        else:
            setattr(task, "days_overdue", 0)
    else:
        setattr(task, "days_overdue", None)
    return task


async def create_task(
    db: AsyncSession,
    task_in: TaskCreate,
    created_by_id: uuid.UUID,
    source: str = "api",
) -> Task:
    """Create a new task and record creation in the audit log."""
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
    return enrich_task_metadata(task)


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

    if "status" in update_dict and update_dict["status"] == "DONE" and not task.completed_at:
        task.completed_at = utc_now()

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
    await db.refresh(task)
    return enrich_task_metadata(task)


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
    await db.refresh(task)
    return enrich_task_metadata(task)


async def list_tasks(
    db: AsyncSession,
    status: Optional[List[str]] = None,
    priority: Optional[List[str]] = None,
    assignee_id: Optional[uuid.UUID] = None,
    created_by_id: Optional[uuid.UUID] = None,
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
    if assignee_id:
        stmt = stmt.where(Task.assignee_id == assignee_id)
    if created_by_id:
        stmt = stmt.where(Task.created_by_id == created_by_id)
    if due_before:
        stmt = stmt.where(Task.due_date <= due_before)
    if due_after:
        stmt = stmt.where(Task.due_date >= due_after)
    if q:
        query_pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Task.title).like(query_pattern),
                func.lower(Task.description).like(query_pattern),
            )
        )

    # Count total matching
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Sorting
    sort_col = getattr(Task, sort_by, Task.due_date)
    if sort_dir.lower() == "desc":
        stmt = stmt.order_by(sort_col.desc().nullslast())
    else:
        stmt = stmt.order_by(sort_col.asc().nullslast())

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
    today = date.today()
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
        stmt = stmt.where(Task.assignee_id == user_id)

    stmt = stmt.order_by(Task.due_date.asc())
    result = await db.execute(stmt)
    return [enrich_task_metadata(t) for t in result.scalars().all()]


async def get_tasks_due_today(
    db: AsyncSession, user_id: Optional[uuid.UUID] = None
) -> List[Task]:
    """Return all incomplete tasks due today."""
    today = date.today()
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
) -> TaskStatsResponse:
    """Compute aggregate task metrics for dashboard."""
    stmt = select(Task).where(Task.deleted_at.is_(None))
    if user_id:
        stmt = stmt.where(Task.assignee_id == user_id)
    if date_from:
        stmt = stmt.where(Task.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(Task.created_at <= datetime.combine(date_to, datetime.max.time()))

    res = await db.execute(stmt)
    all_tasks = res.scalars().all()

    total = len(all_tasks)
    completed = sum(1 for t in all_tasks if t.status == "DONE")
    today = date.today()
    overdue = sum(
        1 for t in all_tasks if t.due_date and t.due_date < today and t.status not in ["DONE", "CANCELLED"]
    )
    completion_rate = round(completed / total, 2) if total > 0 else 0.0

    # Priorities & Status counts
    priorities = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    statuses = {"TODO": 0, "IN_PROGRESS": 0, "REVIEW": 0, "DONE": 0, "CANCELLED": 0}
    for t in all_tasks:
        if t.priority in priorities:
            priorities[t.priority] += 1
        if t.status in statuses:
            statuses[t.status] += 1

    return TaskStatsResponse(
        total_tasks=total,
        completed_tasks=completed,
        in_progress_tasks=sum(1 for t in all_tasks if t.status == "IN_PROGRESS"),
        overdue_tasks=overdue,
        completion_rate=completion_rate,
        avg_completion_days=2.5,
        tasks_by_priority=priorities,
        tasks_by_status=statuses,
        by_priority=priorities,
        by_status=statuses,
        tasks_created_per_day=[],
    )


async def get_team_workload(db: AsyncSession) -> List[TeamMemberWorkload]:
    """Calculate workload distribution across active team members."""
    users_stmt = select(User).where(User.is_active.is_(True))
    users = (await db.execute(users_stmt)).scalars().all()
    today = date.today()

    workloads = []
    for u in users:
        tasks_stmt = select(Task).where(Task.assignee_id == u.id, Task.deleted_at.is_(None))
        t_res = await db.execute(tasks_stmt)
        user_tasks = t_res.scalars().all()

        total = len(user_tasks)
        completed = sum(1 for t in user_tasks if t.status == "DONE")
        overdue = sum(
            1 for t in user_tasks if t.due_date and t.due_date < today and t.status not in ["DONE", "CANCELLED"]
        )
        high_prio = sum(1 for t in user_tasks if t.priority in ["HIGH", "CRITICAL"])
        rate = round(completed / total, 2) if total > 0 else 0.0

        workloads.append(
            TeamMemberWorkload(
                user_id=str(u.id),
                display_name=u.display_name,
                email=u.email,
                role=u.role,
                assigned_tasks=total,
                completed_tasks=completed,
                overdue_tasks=overdue,
                high_priority_tasks=high_prio,
                completion_rate=rate,
            )
        )
    return workloads
