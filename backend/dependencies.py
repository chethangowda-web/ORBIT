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
    from auth.rbac import Role

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = Role.from_str(current_user.role).value
        allowed = [Role.from_str(r).value for r in allowed_roles]
        if user_role not in allowed:
            raise PermissionDeniedException(
                f"Role '{user_role}' is not authorized to access this resource."
            )
        return current_user

    return role_checker
