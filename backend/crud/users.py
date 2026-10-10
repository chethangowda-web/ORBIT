"""
User CRUD Layer
Database access operations for User and UserPreference entities.
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_password_hash
from db.models import User, UserPreference
from schemas.user import AdminUserUpdate, UserCreate, UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    """Retrieve user by primary key UUID."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Retrieve user by exact email match."""
    stmt = select(User).where(func.lower(User.email) == email.lower().strip())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_google_id(db: AsyncSession, google_id: str) -> Optional[User]:
    """Retrieve user by Google Chat identifier."""
    stmt = select(User).where(User.google_id == google_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_by_name(db: AsyncSession, name_query: str) -> Optional[User]:
    """Retrieve user by full or partial name match (case-insensitive)."""
    clean_name = name_query.strip().lower()
    pattern = f"%{clean_name}%"
    stmt = select(User).where(
        or_(
            func.lower(User.display_name).like(pattern),
            func.lower(User.first_name).like(pattern),
            func.lower(User.last_name).like(pattern),
            func.lower(User.email).like(pattern),
        ),
        User.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_all_users(
    db: AsyncSession,
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[User]:
    """List users with optional search, role filter, and pagination."""
    stmt = select(User)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.display_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    stmt = stmt.order_by(User.display_name.asc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_users(
    db: AsyncSession,
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[List[User], int]:
    """Paginated user directory with search and filters; returns (rows, total)."""
    stmt = select(User)
    if q:
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.display_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    if role:
        stmt = stmt.where(User.role == role.strip().lower())
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(User.display_name.asc()).offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total


async def get_user_preferences(db: AsyncSession, user_id: uuid.UUID) -> Dict[str, str]:
    """Return a user's stored preferences as a key/value mapping."""
    rows = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    return {p.key: p.value for p in rows.scalars().all()}


async def admin_update_user(db: AsyncSession, user: User, changes: AdminUserUpdate) -> User:
    """Apply administrator-only changes (role, active flag)."""
    data = changes.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is not None:
            setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Create a new user account."""
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        first_name=user_in.first_name,
        last_name=user_in.last_name,
        role=user_in.role,
        timezone=user_in.timezone,
        google_id=user_in.google_id,
        google_space_id=user_in.google_space_id,
        avatar_url=user_in.avatar_url,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession, user: User, user_update: UserUpdate
) -> User:
    """Update profile attributes for an existing user."""
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


async def update_user_preferences(
    db: AsyncSession, user_id: uuid.UUID, preferences: Dict[str, str]
) -> None:
    """Set or update key-value preferences for a user."""
    for key, value in preferences.items():
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id, UserPreference.key == key
        )
        res = await db.execute(stmt)
        pref = res.scalar_one_or_none()
        if pref:
            pref.value = str(value)
        else:
            db.add(UserPreference(user_id=user_id, key=key, value=str(value)))
    await db.commit()
