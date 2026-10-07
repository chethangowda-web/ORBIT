"""
ORBIT Task Management Endpoints
Provides task CRUD, state transitions, filtering, and audit history.
"""

import math
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud import audit as audit_crud
from crud import tasks as task_crud
from db.models import User
from db.session import get_db
from dependencies import get_current_user, require_role
from exceptions import EntityNotFoundException
from schemas.common import PaginationMeta, api_response
from schemas.task import (
    TaskAuditRead,
    TaskCompleteRequest,
    TaskCreate,
    TaskDetailRead,
    TaskRead,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_tasks(
    status: Optional[List[str]] = Query(None),
    priority: Optional[List[str]] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    created_by_id: Optional[uuid.UUID] = Query(None),
    due_before: Optional[date] = Query(None),
    due_after: Optional[date] = Query(None),
    q: Optional[str] = Query(None),
    include_completed: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("due_date"),
    sort_dir: str = Query("asc"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks with dynamic filtering, sorting, and pagination."""
    tasks, total = await task_crud.list_tasks(
        db=db,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        created_by_id=created_by_id,
        due_before=due_before,
        due_after=due_after,
        q=q,
        include_completed=include_completed,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )
    task_reads = [TaskRead.model_validate(t).model_dump() for t in tasks]
    return api_response(data=task_reads, meta=meta)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_new_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task and record creation in audit trail."""
    task = await task_crud.create_task(
        db=db,
        task_in=payload,
        created_by_id=current_user.id,
        source="api",
    )
    return api_response(data=TaskRead.model_validate(task).model_dump())


@router.get("/overdue", status_code=status.HTTP_200_OK)
async def get_overdue_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all incomplete overdue tasks."""
    tasks = await task_crud.get_overdue_tasks(db=db)
    task_reads = [TaskRead.model_validate(t).model_dump() for t in tasks]
    return api_response(data=task_reads)


@router.get("/{task_id}", status_code=status.HTTP_200_OK)
async def get_task_details(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single task details including its full audit trail."""
    task = await task_crud.get_task(db=db, task_id=task_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)

    return api_response(data=TaskDetailRead.model_validate(task).model_dump())


@router.patch("/{task_id}", status_code=status.HTTP_200_OK)
async def update_task_details(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially update task fields and log changed attributes."""
    task = await task_crud.update_task(
        db=db,
        task_id=task_id,
        task_update=payload,
        user_id=current_user.id,
        source="api",
    )
    return api_response(data=TaskRead.model_validate(task).model_dump())


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("manager", "admin")),
):
    """Soft-delete a task (restricted to managers and admins)."""
    await task_crud.soft_delete_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
        source="api",
    )
    return api_response(data={"message": f"Task {task_id} successfully deleted."})


@router.post("/{task_id}/complete", status_code=status.HTTP_200_OK)
async def mark_task_complete(
    task_id: uuid.UUID,
    payload: TaskCompleteRequest = TaskCompleteRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a task as completed."""
    task = await task_crud.complete_task(
        db=db,
        task_id=task_id,
        user_id=current_user.id,
        completion_note=payload.completion_note,
        source="api",
    )
    return api_response(data=TaskRead.model_validate(task).model_dump())


@router.get("/{task_id}/history", status_code=status.HTTP_200_OK)
async def get_task_history(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full chronological audit trail for a task."""
    history = await audit_crud.get_task_audit_history(db=db, task_id=task_id)
    history_reads = [TaskAuditRead.model_validate(h).model_dump() for h in history]
    return api_response(data=history_reads)
