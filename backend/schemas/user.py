"""
User Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, EmailStr


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
    """Properties for updating user profile."""

    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None
    google_space_id: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None


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


class UserRead(UserBase):
    """Full user representation returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    google_id: Optional[str] = None
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
