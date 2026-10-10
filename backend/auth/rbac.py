"""ORBIT Centralized Role-Based Access Control (RBAC) & Object-Level Permissions Engine.

Enforces resource-level authorization across REST endpoints and LangGraph agent tools.
"""

from enum import Enum
import uuid
from typing import Any, Callable, List, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, User
from exceptions import EntityNotFoundException, PermissionDeniedException


class Role(str, Enum):
    """Normalized application roles."""

    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"

    @classmethod
    def from_str(cls, val: Optional[str]) -> "Role":
        """Normalizes case and maps values cleanly to Role enum."""
        if not val:
            return cls.EMPLOYEE
        normalized = val.strip().lower()
        for role in cls:
            if role.value == normalized:
                return role
        return cls.EMPLOYEE


class TaskAction(str, Enum):
    """Task operations requiring permission validation."""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    ASSIGN = "assign"
    DELETE = "delete"
    COMPLETE = "complete"


def is_admin(user: User) -> bool:
    return Role.from_str(user.role) == Role.ADMIN


def is_manager(user: User) -> bool:
    return Role.from_str(user.role) in (Role.ADMIN, Role.MANAGER)


def can_assign_to_others(user: User) -> bool:
    """Only Admins and Managers can assign tasks to other users."""
    return Role.from_str(user.role) in (Role.ADMIN, Role.MANAGER)


def can_manage_users(user: User) -> bool:
    """Only Admins can manage all users and assign roles."""
    return Role.from_str(user.role) == Role.ADMIN


def can_view_system_settings(user: User) -> bool:
    """Only Admins and Managers can view system settings and scheduler controls."""
    return Role.from_str(user.role) in (Role.ADMIN, Role.MANAGER)


def can_access_team_analytics(user: User) -> bool:
    """Only Admins and Managers can view team-wide workload analytics."""
    return Role.from_str(user.role) in (Role.ADMIN, Role.MANAGER)


def check_task_permission(task: Task, user: User, action: TaskAction) -> bool:
    """Evaluates whether the given user has permission to perform an action on a specific task."""
    user_role = Role.from_str(user.role)

    # 1. Admins have full access across the entire scope
    if user_role == Role.ADMIN:
        return True

    # 2. Managers have access to their created/assigned tasks and team tasks
    if user_role == Role.MANAGER:
        return True

    # 3. Employee permissions
    if user_role == Role.EMPLOYEE:
        is_owner = (task.assignee_id == user.id) or (task.created_by_id == user.id)
        if action == TaskAction.VIEW:
            return is_owner
        elif action in (TaskAction.UPDATE, TaskAction.COMPLETE):
            return is_owner
        elif action == TaskAction.DELETE:
            return False
        elif action == TaskAction.ASSIGN:
            return False

    return False


async def get_authorized_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    user: User,
    action: TaskAction,
) -> Task:
    """Retrieves task from database and enforces object-level authorization.
    
    Raises:
        EntityNotFoundException (404) if task does not exist or was deleted.
        PermissionDeniedException (403) if user is unauthorized.
    """
    from crud import tasks as task_crud

    task = await task_crud.get_task(db=db, task_id=task_id)
    if not task:
        raise EntityNotFoundException("Task", task_id)

    if not check_task_permission(task, user, action):
        raise PermissionDeniedException(
            f"You do not have permission to {action.value} this task."
        )

    return task
