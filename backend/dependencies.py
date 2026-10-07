"""
ORBIT FastAPI Route Dependencies
Provides database session, user authentication, and role authorization dependencies.
"""

import uuid
from typing import Callable, List
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import decode_access_token
from db.models import User
from db.session import get_db
from exceptions import AuthenticationException, PermissionDeniedException

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return the currently authenticated user."""
    if not credentials:
        raise AuthenticationException("Authorization header is missing")

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise AuthenticationException("Invalid or expired token")

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise AuthenticationException("Token missing subject identifier")

    try:
        user_id = uuid.UUID(str(user_id_raw))
    except ValueError:
        raise AuthenticationException("Invalid user ID in token")

    stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationException("User not found or account is deactivated")

    return user


def require_role(*allowed_roles: str) -> Callable:
    """Return a dependency that enforces user role authorization."""

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedException(
                f"Role '{current_user.role}' is not authorized. Required: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker
