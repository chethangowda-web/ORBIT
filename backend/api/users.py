"""ORBIT User Management Endpoints.

Directory lookups for everyone, self-service profile edits, and administrator
controls for roles and account status.
"""

import math
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import Role, is_manager
from crud import tasks as task_crud
from crud import users as user_crud
from db.models import User
from db.session import get_db
from dependencies import get_current_user, require_role
from exceptions import EntityNotFoundException, OrbitException, PermissionDeniedException
from schemas.common import PaginationMeta, api_response
from schemas.task import TaskRead
from schemas.user import (
    AdminUserUpdate,
    UserPreferenceUpdate,
    UserPublic,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_users(
    q: Optional[str] = Query(None, max_length=100),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Directory of users. Only managers and admins can see deactivated accounts."""
    if not is_manager(current_user):
        is_active = True

    users, total = await user_crud.list_users(
        db=db, q=q, role=role, is_active=is_active, page=page, page_size=page_size
    )
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
    data = [UserPublic.model_validate(u).model_dump() for u in users]
    return api_response(data=data, meta=meta)


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Full profile of the authenticated caller."""
    return api_response(data=UserRead.model_validate(current_user).model_dump())


@router.patch("/me", status_code=status.HTTP_200_OK)
async def update_my_profile(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update self-service profile attributes (name, timezone)."""
    updated_user = await user_crud.update_user(db=db, user=current_user, user_update=payload)
    return api_response(data=UserRead.model_validate(updated_user).model_dump())


@router.patch("/me/preferences", status_code=status.HTTP_200_OK)
async def update_my_preferences(
    payload: UserPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update key-value preferences for the current user."""
    await user_crud.update_user_preferences(
        db=db, user_id=current_user.id, preferences=payload.preferences
    )
    return api_response(data={"message": "Preferences updated successfully."})


@router.get("/me/preferences", status_code=status.HTTP_200_OK)
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return stored preferences for the current user."""
    prefs = await user_crud.get_user_preferences(db=db, user_id=current_user.id)
    return api_response(data=prefs)


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def get_user_by_id(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Directory entry for a user; managers and admins also see account details."""
    user = await user_crud.get_user_by_id(db=db, user_id=user_id)
    if not user or (not user.is_active and not is_manager(current_user)):
        raise EntityNotFoundException("User", user_id)
    schema = UserRead if is_manager(current_user) else UserPublic
    return api_response(data=schema.model_validate(user).model_dump())


@router.patch("/{user_id}", status_code=status.HTTP_200_OK)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Change a user's role or active status (admin only, with lockout safeguards)."""
    target = await user_crud.get_user_by_id(db=db, user_id=user_id)
    if not target:
        raise EntityNotFoundException("User", user_id)

    demoting = payload.role is not None and Role.from_str(payload.role) != Role.ADMIN
    deactivating = payload.is_active is False
    target_is_admin = Role.from_str(target.role) == Role.ADMIN

    if target.id == current_user.id and (demoting or deactivating):
        raise OrbitException(
            "You cannot remove your own admin access or deactivate your own account.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if target_is_admin and target.is_active and (demoting or deactivating):
        active_admins = (
            await db.execute(
                select(func.count())
                .select_from(User)
                .where(User.role == Role.ADMIN.value, User.is_active.is_(True))
            )
        ).scalar_one()
        if active_admins <= 1:
            raise OrbitException(
                "At least one active admin must remain.",
                status_code=status.HTTP_409_CONFLICT,
            )

    updated = await user_crud.admin_update_user(db=db, user=target, changes=payload)
    return api_response(data=UserRead.model_validate(updated).model_dump())


@router.patch("/{user_id}/role", status_code=status.HTTP_200_OK, deprecated=True)
async def update_user_role(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Deprecated alias of PATCH /users/{id}; kept for existing clients."""
    return await admin_update_user(
        user_id=user_id, payload=payload, db=db, current_user=current_user
    )


@router.get("/{user_id}/tasks", status_code=status.HTTP_200_OK)
async def get_tasks_for_user(
    user_id: uuid.UUID,
    include_completed: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tasks assigned to a user; employees may only query themselves."""
    if Role.from_str(current_user.role) == Role.EMPLOYEE and user_id != current_user.id:
        raise PermissionDeniedException("Employees cannot view tasks assigned to other users.")

    tasks, _ = await task_crud.list_tasks(
        db=db,
        assignee_id=user_id,
        include_completed=include_completed,
        page_size=100,
    )
    return api_response(data=[TaskRead.model_validate(t).model_dump() for t in tasks])
