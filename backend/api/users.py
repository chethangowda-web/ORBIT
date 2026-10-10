"""ORBIT User Management Endpoints.

Provides user discovery, profile retrieval, preference updating, assigned task queries,
and administrative role management.
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import Role
from crud import tasks as task_crud
from crud import users as user_crud
from db.models import User
from db.session import get_db
from dependencies import get_current_user, require_role
from exceptions import EntityNotFoundException, PermissionDeniedException
from schemas.common import api_response
from schemas.task import TaskRead
from schemas.user import UserPreferenceUpdate, UserRead, UserRoleUpdate, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_users(
    q: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List system users with optional search and role filtering."""
    users = await user_crud.get_all_users(
        db=db, q=q, role=role, is_active=is_active, skip=skip, limit=limit
    )
    user_reads = [UserRead.model_validate(u).model_dump() for u in users]
    return api_response(data=user_reads)


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Return profile of the authenticated caller."""
    return api_response(data=UserRead.model_validate(current_user).model_dump())


@router.patch("/me", status_code=status.HTTP_200_OK)
async def update_my_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update profile attributes of the authenticated caller."""
    updated_user = await user_crud.update_user(
        db=db, user=current_user, user_update=payload
    )
    return api_response(data=UserRead.model_validate(updated_user).model_dump())


@router.patch("/me/preferences", status_code=status.HTTP_200_OK)
async def update_my_preferences(
    payload: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update key-value preferences for current user."""
    await user_crud.update_user_preferences(
        db=db, user_id=current_user.id, preferences=payload.preferences
    )
    return api_response(data={"message": "Preferences updated successfully."})


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a user by UUID."""
    user = await user_crud.get_user_by_id(db=db, user_id=user_id)
    if not user:
        raise EntityNotFoundException("User", user_id)
    return api_response(data=UserRead.model_validate(user).model_dump())


@router.patch("/{user_id}/role", status_code=status.HTTP_200_OK)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Update user role (restricted strictly to Admins)."""
    target_user = await user_crud.get_user_by_id(db=db, user_id=user_id)
    if not target_user:
        raise EntityNotFoundException("User", user_id)

    normalized_role = Role.from_str(payload.role).value
    target_user.role = normalized_role
    await db.commit()
    await db.refresh(target_user)
    return api_response(data=UserRead.model_validate(target_user).model_dump())


@router.get("/{user_id}/tasks", status_code=status.HTTP_200_OK)
async def get_tasks_for_user(
    user_id: uuid.UUID,
    include_completed: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve tasks assigned to a specific user with role authorization check."""
    # Policy: Employees cannot view other users' task lists
    if Role.from_str(current_user.role) == Role.EMPLOYEE and user_id != current_user.id:
        raise PermissionDeniedException("Employees cannot view tasks assigned to other users.")

    tasks, _ = await task_crud.list_tasks(
        db=db,
        assignee_id=user_id,
        include_completed=include_completed,
        page_size=100,
    )
    task_reads = [TaskRead.model_validate(t).model_dump() for t in tasks]
    return api_response(data=task_reads)
