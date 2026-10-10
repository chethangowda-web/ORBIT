"""
Authentication Pydantic Schemas
"""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    password: str = Field(..., min_length=10, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=255)
    timezone: str = "Asia/Kolkata"


class GoogleAuthUrlResponse(BaseModel):
    """Response containing Google OAuth authorization URL."""

    authorization_url: str
    state: str


class GoogleCallbackRequest(BaseModel):
    """Payload for exchanging Google OAuth authorization code."""

    code: str
    state: str


class GoogleAccountLinkRequest(BaseModel):
    """Payload for linking an existing password-authenticated account to Google."""

    link_token: str
    password: str
