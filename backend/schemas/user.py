"""
User Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_timezone(value: Optional[str]) -> Optional[str]:
    """Reject unknown IANA timezone names."""
    if value is None:
        return value
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone '{value}'") from exc
    return value


class UserBase(BaseModel):
    """Base user properties."""

    email: EmailStr
    display_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "employee"
    timezone: str = "Asia/Kolkata"
    google_space_id: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    """Properties required on user creation."""

    password: str
    google_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Profile fields a user may change about themselves.

    Privilege and routing fields (role, is_active, google ids, chat space) are
    deliberately absent: they are managed by administrators or by sign-in flows.
    """

    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = None

    _tz = field_validator("timezone")(_validate_timezone)


class AdminUserUpdate(BaseModel):
    """Administrative changes to another user's account."""

    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _role_known(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value.strip().lower() not in {"admin", "manager", "employee"}:
            raise ValueError("role must be one of: admin, manager, employee")
        return value.strip().lower() if value else value


class UserPreferenceUpdate(BaseModel):
    """Preferences update request."""

    preferences: Dict[str, str]


class UserRoleUpdate(BaseModel):
    """Administrative role update request."""

    role: str


class UserSummary(BaseModel):
    """Minimal user summary model for references and lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: str
    google_space_id: Optional[str] = None


class UserPublic(BaseModel):
    """Directory view of a user: enough to assign and display, nothing sensitive."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: str
    avatar_url: Optional[str] = None
    is_active: bool = True


class UserRead(UserBase):
    """Full user representation returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    google_id: Optional[str] = None
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
