"""
Task Management Agent Tools
LangChain-compatible tools wrapping Task CRUD operations for agent execution.
"""

import uuid
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Union
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from crud import tasks as task_crud
from crud import users as user_crud
from schemas.task import (
    TaskCreate,
    TaskDetailRead,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from tools.base import ToolResult, get_tool_session, tool_error, tool_success


def to_uuid(val: Optional[Union[str, uuid.UUID]]) -> Optional[uuid.UUID]:
    """Convert string or UUID instance to uuid.UUID object."""
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


class CreateTaskInput(BaseModel):
    """Input parameters for creating a new task."""

    title: str = Field(..., description="Actionable title of the task (max 255 chars)")
    description: Optional[str] = Field(None, description="Detailed explanation or requirements of the task")
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        default="MEDIUM", description="Priority level: LOW, MEDIUM, HIGH, or CRITICAL"
    )
    assignee_id: Optional[Union[str, uuid.UUID]] = Field(None, description="UUID of the assignee if known")
    assignee_name: Optional[str] = Field(None, description="Name of the person to assign this task to (e.g. 'John')")
    due_date: Optional[Union[date, str]] = Field(None, description="Due date in ISO YYYY-MM-DD format")
    created_by_id: Union[str, uuid.UUID] = Field(..., description="UUID of the user creating the task")
    tags: List[str] = Field(default_factory=list, description="Labels or category tags")


class GetTaskInput(BaseModel):
    """Input for retrieving a task by UUID."""

    task_id: Union[str, uuid.UUID] = Field(..., description="UUID of the task")


class UpdateTaskInput(BaseModel):
    """Input parameters for modifying an existing task."""

    task_id: Union[str, uuid.UUID] = Field(..., description="UUID of the task to update")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(None, description="New description")
    priority: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = Field(None, description="New priority")
    assignee_id: Optional[Union[str, uuid.UUID]] = Field(None, description="New assignee UUID")
    assignee_name: Optional[str] = Field(None, description="New assignee name to resolve")
    due_date: Optional[Union[date, str]] = Field(None, description="New due date (YYYY-MM-DD)")
    status: Optional[Literal["TODO", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED"]] = Field(None, description="New status")
    tags: Optional[List[str]] = Field(None, description="Updated list of tags")
    updated_by_id: Union[str, uuid.UUID] = Field(..., description="UUID of the user performing this update")


class CompleteTaskInput(BaseModel):
    """Input for marking a task as DONE."""

    task_id: Union[str, uuid.UUID] = Field(..., description="UUID of the task to complete")
    completed_by_id: Union[str, uuid.UUID] = Field(..., description="UUID of the user completing the task")
    completion_note: Optional[str] = Field(None, description="Optional note or summary of completion")


class DeleteTaskInput(BaseModel):
    """Input for soft-deleting a task."""

    task_id: Union[str, uuid.UUID] = Field(..., description="UUID of the task to delete")
    deleted_by_id: Union[str, uuid.UUID] = Field(..., description="UUID of the user requesting deletion")
    reason: Optional[str] = Field(None, description="Reason for deleting the task")


class SearchTasksInput(BaseModel):
    """Input for searching tasks with filters."""

    query: Optional[str] = Field(None, description="Full-text or title search term")
    assignee_id: Optional[Union[str, uuid.UUID]] = Field(None, description="UUID of assignee")
    status: Optional[List[str]] = Field(None, description="Filter by statuses, e.g. ['TODO', 'IN_PROGRESS']")
    priority: Optional[List[str]] = Field(None, description="Filter by priorities, e.g. ['HIGH', 'CRITICAL']")
    due_before: Optional[Union[date, str]] = Field(None, description="Tasks due on or before date")
    due_after: Optional[Union[date, str]] = Field(None, description="Tasks due on or after date")
    created_by_id: Optional[Union[str, uuid.UUID]] = Field(None, description="UUID of creator")
    include_completed: bool = Field(default=False, description="Include DONE and CANCELLED tasks")
    limit: int = Field(default=20, description="Max results to return")
    offset: int = Field(default=0, description="Pagination offset")


class GetUserTasksInput(BaseModel):
    """Input for listing tasks assigned to a specific user."""

    user_id: Union[str, uuid.UUID] = Field(..., description="UUID of the user")
    status: List[str] = Field(default=["TODO", "IN_PROGRESS", "REVIEW"], description="List of statuses to include")
    limit: int = Field(default=50, description="Max tasks to return")


class GetOverdueTasksInput(BaseModel):
    """Input for retrieving past-due tasks."""

    user_id: Optional[Union[str, uuid.UUID]] = Field(None, description="Optional user UUID to restrict overdue tasks to")
    limit: int = Field(default=50, description="Max tasks to return")


class GetTasksDueTodayInput(BaseModel):
    """Input for retrieving tasks due today."""

    user_id: Optional[Union[str, uuid.UUID]] = Field(None, description="Optional user UUID to restrict tasks to")


@tool(args_schema=CreateTaskInput)
async def create_task(
    title: str,
    created_by_id: Union[str, uuid.UUID],
    description: Optional[str] = None,
    priority: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM",
    assignee_id: Optional[Union[str, uuid.UUID]] = None,
    assignee_name: Optional[str] = None,
    due_date: Optional[Union[date, str]] = None,
    tags: List[str] = [],
) -> ToolResult:
    """Create a new task in the database with optional assignee resolution and audit logging."""
    try:
        creator_uuid = to_uuid(created_by_id)
        parsed_due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date

        async with get_tool_session() as db:
            from auth.rbac import can_assign_to_others
            target_assignee_id = to_uuid(assignee_id)
            if not target_assignee_id and assignee_name:
                resolved_user = await user_crud.get_user_by_name(db, assignee_name)
                if resolved_user:
                    target_assignee_id = resolved_user.id
            if not target_assignee_id:
                target_assignee_id = creator_uuid

            calling_user = await user_crud.get_user_by_id(db, creator_uuid)
            if calling_user and not can_assign_to_others(calling_user):
                if target_assignee_id and target_assignee_id != creator_uuid:
                    return tool_error("Permission denied: Employees cannot assign tasks to other users.")

            task_in = TaskCreate(
                title=title,
                description=description,
                priority=TaskPriority(priority),
                assignee_id=target_assignee_id,
                due_date=parsed_due,
                tags=tags,
            )
            created = await task_crud.create_task(
                db=db, task_in=task_in, created_by_id=creator_uuid, source="chat"
            )
            return tool_success(data=TaskRead.model_validate(created).model_dump())
    except Exception as e:
        return tool_error(f"Failed to create task '{title}': {str(e)}")


@tool(args_schema=GetTaskInput)
async def get_task_by_id(task_id: Union[str, uuid.UUID]) -> ToolResult:
    """Retrieve full details of a task by its UUID including its audit trail."""
    try:
        t_uuid = to_uuid(task_id)
        async with get_tool_session() as db:
            task = await task_crud.get_task(db, t_uuid)
            if not task:
                return tool_error(f"Task with ID {task_id} was not found.")
            return tool_success(data=TaskDetailRead.model_validate(task).model_dump())
    except Exception as e:
        return tool_error(f"Error retrieving task {task_id}: {str(e)}")


@tool(args_schema=UpdateTaskInput)
async def update_task(
    task_id: Union[str, uuid.UUID],
    updated_by_id: Union[str, uuid.UUID],
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]] = None,
    assignee_id: Optional[Union[str, uuid.UUID]] = None,
    assignee_name: Optional[str] = None,
    due_date: Optional[Union[date, str]] = None,
    status: Optional[Literal["TODO", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED"]] = None,
    tags: Optional[List[str]] = None,
) -> ToolResult:
    """Update fields on an existing task and record diffs in the audit log."""
    try:
        t_uuid = to_uuid(task_id)
        user_uuid = to_uuid(updated_by_id)
        parsed_due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date

        async with get_tool_session() as db:
            from auth.rbac import TaskAction, can_assign_to_others, check_task_permission, is_manager
            existing_task = await task_crud.get_task(db, t_uuid)
            if not existing_task:
                return tool_error(f"Task with ID {task_id} was not found.")

            calling_user = await user_crud.get_user_by_id(db, user_uuid)
            if calling_user and not check_task_permission(existing_task, calling_user, TaskAction.UPDATE):
                return tool_error(f"Permission denied: You cannot update task {task_id}.")

            target_assignee_id = to_uuid(assignee_id)
            if not target_assignee_id and assignee_name:
                resolved_user = await user_crud.get_user_by_name(db, assignee_name)
                if resolved_user:
                    target_assignee_id = resolved_user.id

            if calling_user and not can_assign_to_others(calling_user):
                if target_assignee_id is not None and target_assignee_id != user_uuid:
                    return tool_error("Permission denied: Employees cannot reassign tasks to other users.")

            update_fields: Dict[str, Any] = {}
            if title is not None:
                update_fields["title"] = title
            if description is not None:
                update_fields["description"] = description
            if priority is not None:
                update_fields["priority"] = TaskPriority(priority)
            if target_assignee_id is not None:
                update_fields["assignee_id"] = target_assignee_id
            if parsed_due is not None:
                update_fields["due_date"] = parsed_due
            if status is not None:
                update_fields["status"] = TaskStatus(status)
            if tags is not None:
                update_fields["tags"] = tags

            task_update = TaskUpdate(**update_fields)
            updated = await task_crud.update_task(
                db=db, task_id=t_uuid, task_update=task_update, user_id=user_uuid, source="chat"
            )
            return tool_success(data=TaskRead.model_validate(updated).model_dump())
    except Exception as e:
        return tool_error(f"Failed to update task {task_id}: {str(e)}")


@tool(args_schema=CompleteTaskInput)
async def complete_task(
    task_id: Union[str, uuid.UUID],
    completed_by_id: Union[str, uuid.UUID],
    completion_note: Optional[str] = None,
) -> ToolResult:
    """Mark a task as DONE and record the completion timestamp."""
    try:
        t_uuid = to_uuid(task_id)
        user_uuid = to_uuid(completed_by_id)

        async with get_tool_session() as db:
            from auth.rbac import TaskAction, check_task_permission
            existing_task = await task_crud.get_task(db, t_uuid)
            if not existing_task:
                return tool_error(f"Task with ID {task_id} was not found.")

            calling_user = await user_crud.get_user_by_id(db, user_uuid)
            if calling_user and not check_task_permission(existing_task, calling_user, TaskAction.COMPLETE):
                return tool_error(f"Permission denied: You cannot complete task {task_id}.")

            completed = await task_crud.complete_task(
                db=db,
                task_id=t_uuid,
                user_id=user_uuid,
                completion_note=completion_note,
                source="chat",
            )
            return tool_success(data=TaskRead.model_validate(completed).model_dump())
    except Exception as e:
        return tool_error(f"Failed to complete task {task_id}: {str(e)}")


@tool(args_schema=DeleteTaskInput)
async def delete_task(
    task_id: Union[str, uuid.UUID],
    deleted_by_id: Union[str, uuid.UUID],
    reason: Optional[str] = None,
) -> ToolResult:
    """Soft-delete a task from the active task list."""
    try:
        t_uuid = to_uuid(task_id)
        user_uuid = to_uuid(deleted_by_id)

        async with get_tool_session() as db:
            from auth.rbac import is_manager
            calling_user = await user_crud.get_user_by_id(db, user_uuid)
            if not calling_user or not is_manager(calling_user):
                return tool_error("Permission denied: Only managers and admins can delete tasks.")

            deleted = await task_crud.soft_delete_task(
                db=db, task_id=t_uuid, user_id=user_uuid, source="chat"
            )
            return tool_success(data={"deleted_id": str(deleted.id), "reason": reason})
    except Exception as e:
        return tool_error(f"Failed to delete task {task_id}: {str(e)}")


@tool(args_schema=SearchTasksInput)
async def search_tasks(
    query: Optional[str] = None,
    assignee_id: Optional[Union[str, uuid.UUID]] = None,
    status: Optional[List[str]] = None,
    priority: Optional[List[str]] = None,
    due_before: Optional[Union[date, str]] = None,
    due_after: Optional[Union[date, str]] = None,
    created_by_id: Optional[Union[str, uuid.UUID]] = None,
    include_completed: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> ToolResult:
    """Search tasks across titles and descriptions with multi-attribute filtering."""
    try:
        parsed_assignee = to_uuid(assignee_id)
        parsed_creator = to_uuid(created_by_id)
        p_before = date.fromisoformat(due_before) if isinstance(due_before, str) else due_before
        p_after = date.fromisoformat(due_after) if isinstance(due_after, str) else due_after
        page = (offset // limit) + 1 if limit > 0 else 1

        async with get_tool_session() as db:
            tasks, total = await task_crud.list_tasks(
                db=db,
                status=status,
                priority=priority,
                assignee_id=parsed_assignee,
                created_by_id=parsed_creator,
                due_before=p_before,
                due_after=p_after,
                q=query,
                include_completed=include_completed,
                page=page,
                page_size=limit,
            )
            task_list = [TaskRead.model_validate(t).model_dump() for t in tasks]
            return tool_success(data=task_list, count=total)
    except Exception as e:
        return tool_error(f"Failed to search tasks: {str(e)}")


@tool(args_schema=GetUserTasksInput)
async def get_user_tasks(
    user_id: Union[str, uuid.UUID],
    status: List[str] = ["TODO", "IN_PROGRESS", "REVIEW"],
    limit: int = 50,
) -> ToolResult:
    """Get active tasks assigned to a specific user filtered by status."""
    try:
        u_uuid = to_uuid(user_id)
        async with get_tool_session() as db:
            tasks, total = await task_crud.list_tasks(
                db=db,
                user_id=u_uuid,
                status=status,
                page_size=limit,
                sort_by="updated_at",
                sort_dir="desc",
            )
            task_list = [TaskRead.model_validate(t).model_dump() for t in tasks]
            return tool_success(data=task_list, count=total)
    except Exception as e:
        return tool_error(f"Failed to get tasks for user {user_id}: {str(e)}")


@tool(args_schema=GetOverdueTasksInput)
async def get_overdue_tasks(
    user_id: Optional[Union[str, uuid.UUID]] = None,
    limit: int = 50,
) -> ToolResult:
    """Get all past-due incomplete tasks for a user or the entire organization."""
    try:
        u_uuid = to_uuid(user_id)
        async with get_tool_session() as db:
            tasks = await task_crud.get_overdue_tasks(db=db, user_id=u_uuid)
            task_list = [TaskRead.model_validate(t).model_dump() for t in tasks[:limit]]
            return tool_success(data=task_list, count=len(task_list))
    except Exception as e:
        return tool_error(f"Failed to retrieve overdue tasks: {str(e)}")


@tool(args_schema=GetTasksDueTodayInput)
async def get_tasks_due_today(
    user_id: Optional[Union[str, uuid.UUID]] = None,
) -> ToolResult:
    """Get all tasks that are due today."""
    try:
        u_uuid = to_uuid(user_id)
        async with get_tool_session() as db:
            tasks = await task_crud.get_tasks_due_today(db=db, user_id=u_uuid)
            task_list = [TaskRead.model_validate(t).model_dump() for t in tasks]
            return tool_success(data=task_list, count=len(task_list))
    except Exception as e:
        return tool_error(f"Failed to get tasks due today: {str(e)}")
