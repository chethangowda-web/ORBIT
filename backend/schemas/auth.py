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


from schemas.user import UserSummary


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
