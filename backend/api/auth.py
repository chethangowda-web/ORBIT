"""
ORBIT Authentication Endpoints
Handles user login, registration, and session identity inspection.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import create_access_token, get_password_hash, verify_password
from config import settings
from db.models import User
from db.session import get_db
from dependencies import get_current_user
from exceptions import AuthenticationException, OrbitException
from schemas.auth import (
    TokenRequest,
    TokenResponseData,
    UserRegisterRequest,
    UserSummary,
)
from schemas.common import api_response

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", status_code=status.HTTP_200_OK)
async def login_for_access_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password to receive a JWT access token."""
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise AuthenticationException("Invalid email or password")

    if not verify_password(payload.password, user.hashed_password):
        raise AuthenticationException("Invalid email or password")

    if not user.is_active:
        raise AuthenticationException("Account is inactive")

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    token_data = TokenResponseData(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary.model_validate(user),
    )

    return api_response(data=token_data.model_dump())


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account for testing or administration."""
    existing_stmt = select(User).where(User.email == payload.email)
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise OrbitException(
            "User with this email already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        timezone=payload.timezone,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    token_data = TokenResponseData(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary.model_validate(user),
    )

    return api_response(data=token_data.model_dump())


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return profile details of the authenticated caller."""
    user_summary = UserSummary.model_validate(current_user)
    return api_response(data=user_summary.model_dump())
