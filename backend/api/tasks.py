"""ORBIT Task Management Endpoints.

Provides task CRUD, state transitions, filtering, audit history, and object-level RBAC enforcement.
"""

import math
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import Role, TaskAction, get_authorized_task, is_manager
from config import settings
from crud import attachments as attachment_crud
from crud import audit as audit_crud
from crud import comments as comment_crud
from crud import tasks as task_crud
from db.models import User
from db.session import get_db
from dependencies import get_current_user, require_role
from services import storage
from services.notifications import notify_task_event
from exceptions import EntityNotFoundException, OrbitException, PermissionDeniedException
from schemas.common import PaginationMeta, api_response
from schemas.task import (
    AttachmentRead,
    BulkFailure,
    BulkTaskAction,
    BulkTaskResult,
    CommentCreate,
    CommentRead,
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
    """List tasks with dynamic filtering, sorting, pagination, and employee scope isolation."""
    # Scope query by role: Employees can only view tasks assigned to or created by them
    is_employee = Role.from_str(current_user.role) == Role.EMPLOYEE
    user_filter = current_user.id if is_employee else None

    tasks, total = await task_crud.list_tasks(
        db=db,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        created_by_id=created_by_id,
        user_id=user_filter,
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
    # Policy: Employees cannot assign tasks to other users
    is_employee = Role.from_str(current_user.role) == Role.EMPLOYEE
    if is_employee and payload.assignee_id and payload.assignee_id != current_user.id:
        raise PermissionDeniedException("Employees cannot assign tasks to other users.")

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
    """Return all incomplete overdue tasks scoped to user permissions."""
    is_employee = Role.from_str(current_user.role) == Role.EMPLOYEE
    user_filter = current_user.id if is_employee else None

    tasks = await task_crud.get_overdue_tasks(db=db, user_id=user_filter)
    task_reads = [TaskRead.model_validate(t).model_dump() for t in tasks]
    return api_response(data=task_reads)


@router.get("/{task_id}", status_code=status.HTTP_200_OK)
async def get_task_details(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single task details with object-level authorization."""
    task = await get_authorized_task(
        db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW
    )
    return api_response(data=TaskDetailRead.model_validate(task).model_dump())


@router.patch("/{task_id}", status_code=status.HTTP_200_OK)
async def update_task_details(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially update task fields after object-level authorization check."""
    existing = await get_authorized_task(
        db=db, task_id=task_id, user=current_user, action=TaskAction.UPDATE
    )

    # Policy: employees cannot hand a task to someone else or take it off its assignee. Sending the
    # current assignee back unchanged is fine (the edit form does), and so is assigning to themselves.
    is_employee = Role.from_str(current_user.role) == Role.EMPLOYEE
    if (
        is_employee
        and "assignee_id" in payload.model_fields_set
        and payload.assignee_id != existing.assignee_id
        and payload.assignee_id != current_user.id
    ):
        raise PermissionDeniedException("Employees cannot reassign tasks to other users.")

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
    await get_authorized_task(
        db=db, task_id=task_id, user=current_user, action=TaskAction.DELETE
    )
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
    """Mark a task as completed after checking permissions."""
    await get_authorized_task(
        db=db, task_id=task_id, user=current_user, action=TaskAction.COMPLETE
    )
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
    """Get full chronological audit trail for an authorized task."""
    await get_authorized_task(
        db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW
    )
    history = await audit_crud.get_task_audit_history(db=db, task_id=task_id)
    history_reads = [TaskAuditRead.model_validate(h).model_dump() for h in history]
    return api_response(data=history_reads)


@router.get("/{task_id}/comments", status_code=status.HTTP_200_OK)
async def list_task_comments(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Comments on a task you may view, oldest first."""
    await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    comments = await comment_crud.list_comments(db=db, task_id=task_id)
    return api_response(data=[CommentRead.model_validate(c).model_dump() for c in comments])


@router.post("/{task_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_task_comment(
    task_id: uuid.UUID,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Comment on a task you may view; the assignee and creator are notified."""
    task = await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    comment = await comment_crud.add_comment(db=db, task=task, author=current_user, body=payload.body)

    recipients = {u.id: u for u in (task.assignee, task.creator) if u is not None and u.id != current_user.id}
    for recipient in recipients.values():
        await notify_task_event(
            session=db,
            task=task,
            event_type="task_commented",
            recipient=recipient,
            actor_name=current_user.display_name,
            detail=payload.body if len(payload.body) <= 200 else payload.body[:197] + "...",
        )
    return api_response(data=CommentRead.model_validate(comment).model_dump())


@router.delete("/{task_id}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_task_comment(
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Authors can delete their own comments; managers and admins can delete any."""
    await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    comment = await comment_crud.get_comment(db=db, task_id=task_id, comment_id=comment_id)
    if comment is None:
        raise EntityNotFoundException("Comment", comment_id)
    if comment.author_id != current_user.id and not is_manager(current_user):
        raise PermissionDeniedException("You can only delete your own comments.")
    await comment_crud.delete_comment(db=db, comment=comment)
    return api_response(data={"message": "Comment deleted."})


@router.get("/{task_id}/attachments", status_code=status.HTTP_200_OK)
async def list_task_attachments(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Files attached to a task you may view."""
    await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    items = await attachment_crud.list_attachments(db=db, task_id=task_id)
    return api_response(data=[AttachmentRead.model_validate(a).model_dump() for a in items])


@router.post("/{task_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_task_attachment(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach a file. Requires permission to edit the task; type and size are validated."""
    task = await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.UPDATE)
    filename, content_type = storage.validate_filename(file.filename)
    if await attachment_crud.count_attachments(db=db, task_id=task_id) >= settings.MAX_ATTACHMENTS_PER_TASK:
        raise OrbitException(f"A task can have at most {settings.MAX_ATTACHMENTS_PER_TASK} attachments.", 409)

    stored_name, size = await storage.save_stream(file)
    try:
        attachment = await attachment_crud.add_attachment(
            db=db,
            task=task,
            uploader=current_user,
            filename=filename,
            stored_name=stored_name,
            content_type=content_type,
            size_bytes=size,
        )
    except Exception:
        storage.remove(stored_name)
        raise
    return api_response(data=AttachmentRead.model_validate(attachment).model_dump())


@router.get("/{task_id}/attachments/{attachment_id}", status_code=status.HTTP_200_OK)
async def download_task_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download as an attachment (never rendered inline) with sniffing disabled."""
    await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    attachment = await attachment_crud.get_attachment(db=db, task_id=task_id, attachment_id=attachment_id)
    if attachment is None:
        raise EntityNotFoundException("Attachment", attachment_id)
    path = storage.path_for(attachment.stored_name)
    if not path.is_file():
        raise EntityNotFoundException("Attachment file", attachment_id)
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.delete("/{task_id}/attachments/{attachment_id}", status_code=status.HTTP_200_OK)
async def delete_task_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The uploader, and managers or admins, can remove a file."""
    await get_authorized_task(db=db, task_id=task_id, user=current_user, action=TaskAction.VIEW)
    attachment = await attachment_crud.get_attachment(db=db, task_id=task_id, attachment_id=attachment_id)
    if attachment is None:
        raise EntityNotFoundException("Attachment", attachment_id)
    if attachment.uploaded_by_id != current_user.id and not is_manager(current_user):
        raise PermissionDeniedException("You can only remove files you uploaded.")
    stored_name = attachment.stored_name
    await attachment_crud.delete_attachment(db=db, attachment=attachment, actor=current_user)
    storage.remove(stored_name)
    return api_response(data={"message": "Attachment removed."})


BULK_ACTION_PERMISSION = {
    "complete": TaskAction.COMPLETE,
    "set_status": TaskAction.UPDATE,
    "set_priority": TaskAction.UPDATE,
    # Same rule as PATCH /tasks/{id}: updating is allowed; handing work to others is checked separately.
    "assign": TaskAction.UPDATE,
    "delete": TaskAction.DELETE,
}


async def _apply_bulk_action(db: AsyncSession, user: User, payload: BulkTaskAction, task_id: uuid.UUID) -> None:
    """Apply one bulk action to one task, raising on any permission or business-rule failure."""
    await get_authorized_task(db=db, task_id=task_id, user=user, action=BULK_ACTION_PERMISSION[payload.action])

    if payload.action == "complete":
        await task_crud.complete_task(db=db, task_id=task_id, user_id=user.id, source="api")
    elif payload.action == "delete":
        await task_crud.soft_delete_task(db=db, task_id=task_id, user_id=user.id, source="api")
    elif payload.action == "assign":
        assignee = uuid.UUID(payload.value) if payload.value else None
        if assignee is not None and assignee != user.id and Role.from_str(user.role) == Role.EMPLOYEE:
            raise PermissionDeniedException("Employees cannot assign tasks to other users.")
        await task_crud.update_task(db=db, task_id=task_id, task_update=TaskUpdate(assignee_id=assignee), user_id=user.id, source="api")
    else:
        field = "status" if payload.action == "set_status" else "priority"
        await task_crud.update_task(db=db, task_id=task_id, task_update=TaskUpdate(**{field: payload.value}), user_id=user.id, source="api")


@router.post("/bulk", status_code=status.HTTP_200_OK)
async def bulk_task_action(
    payload: BulkTaskAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply an action to several tasks. Every task is authorised individually and one failure
    never aborts the rest: the response lists which succeeded and why others failed."""
    succeeded: list[uuid.UUID] = []
    failed: list[BulkFailure] = []
    for task_id in dict.fromkeys(payload.task_ids):
        try:
            await _apply_bulk_action(db, current_user, payload, task_id)
            succeeded.append(task_id)
        except (OrbitException, PermissionDeniedException, EntityNotFoundException) as exc:
            # Roll back anything half-applied, then reload the caller: rollback expires every
            # loaded object and the next iteration needs the user's id and role.
            await db.rollback()
            await db.refresh(current_user)
            failed.append(BulkFailure(id=task_id, reason=exc.message))
    return api_response(data=BulkTaskResult(succeeded=succeeded, failed=failed).model_dump(mode="json"))
