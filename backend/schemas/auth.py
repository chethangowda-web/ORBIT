"""
Authentication Pydantic Schemas
"""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class TokenRequest(BaseModel):
    """Payload for requesting JWT authentication token."""

    email: EmailStr
    password: str


class UserSummary(BaseModel):
    """Minimal user information embedded in auth responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    google_space_id: Optional[str] = None


class TokenResponseData(BaseModel):
    """Data payload containing token details and authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


class UserRegisterRequest(BaseModel):
    """Payload for registering a new user."""

    email: EmailStr
    password: str
    display_name: str
    role: str = "employee"
    timezone: str = "Asia/Kolkata"
