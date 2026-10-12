"""ORBIT Authentication Endpoints.

Handles user login, registration, Google OAuth 2.0 / OpenID Connect PKCE flow,
account linking, and session identity inspection.
"""

import secrets
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import google_oauth
from auth.jwt import create_access_token, get_password_hash, verify_password
from auth.ratelimit import clear_login_failures, enforce_login_rate_limit, record_login_failure
from auth.rbac import Role
from config import settings
from db.base import utc_now
from db.models import User
from db.session import get_db
from dependencies import get_current_user
from exceptions import AuthenticationException, OrbitException
from schemas.auth import (
    GoogleAccountLinkRequest,
    GoogleAuthUrlResponse,
    GoogleCallbackRequest,
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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password to receive a JWT access token."""
    await enforce_login_rate_limit(request, payload.email)
    stmt = select(User).where(func.lower(User.email) == payload.email.lower())
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if (
        not user
        or not user.hashed_password
        or not verify_password(payload.password, user.hashed_password)
    ):
        await record_login_failure(request, payload.email)
        raise AuthenticationException("Invalid email or password")

    if not user.is_active:
        raise AuthenticationException("Account is inactive")

    await clear_login_failures(request, payload.email)
    user.last_seen_at = utc_now()
    await db.commit()

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
    """Register a new user account with default least-privileged role (EMPLOYEE).

    Disabled unless ALLOW_REGISTRATION is true: accounts are normally provisioned
    through Google sign-in, Google Chat, or an administrator.
    """
    if not settings.ALLOW_REGISTRATION:
        raise OrbitException(
            "Self-registration is disabled. Sign in with Google or ask an administrator.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    existing_stmt = select(User).where(func.lower(User.email) == payload.email.lower())
    existing_res = await db.execute(existing_stmt)
    if existing_res.scalar_one_or_none():
        raise OrbitException(
            "User with this email already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    # Force least-privileged role for public self-registration: Admin/Manager cannot be created publicly
    assigned_role = Role.EMPLOYEE.value

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        display_name=payload.display_name,
        role=assigned_role,
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


@router.get("/google/url", status_code=status.HTTP_200_OK)
async def get_google_auth_url(
    response: Response,
):
    """Generates PKCE state, nonce, and Google OAuth authorization URL."""
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise OrbitException(
            "Google OAuth is not configured on this server.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    code_verifier, code_challenge = google_oauth.generate_pkce_pair()

    session_token = google_oauth.create_oauth_session_token(
        state=state, code_verifier=code_verifier, nonce=nonce
    )

    # Store state and code_verifier in HttpOnly cookie
    response.set_cookie(
        key="orbit_oauth_state",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.ENVIRONMENT == "production",
        max_age=600,
        path="/",
    )

    auth_url = google_oauth.build_google_authorization_url(
        state=state, code_challenge=code_challenge, nonce=nonce
    )

    return api_response(
        data=GoogleAuthUrlResponse(authorization_url=auth_url, state=state).model_dump()
    )


@router.post("/google/callback", status_code=status.HTTP_200_OK)
async def google_oauth_callback(
    payload: GoogleCallbackRequest,
    request: Request,
    response: Response,
    orbit_oauth_state: str | None = Cookie(None),
    x_oauth_state: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Exchanges Google authorization code for token, validates identity, and provisions account."""
    cookie_token = (
        request.cookies.get("orbit_oauth_state")
        or orbit_oauth_state
        or x_oauth_state
        or request.headers.get("x-oauth-state")
    )
    if not cookie_token:
        raise AuthenticationException("Missing OAuth state session. Please initiate login again.")

    session_data = google_oauth.verify_oauth_session_token(cookie_token)
    if payload.state != session_data.get("state"):
        raise AuthenticationException("Invalid OAuth state parameter.")

    # Clear state cookie
    response.delete_cookie(key="orbit_oauth_state", path="/")

    # 1. Exchange authorization code with Google for tokens
    code_verifier = session_data["code_verifier"]
    token_response = await google_oauth.exchange_google_code(
        code=payload.code, code_verifier=code_verifier
    )

    id_token_jwt = token_response.get("id_token")
    if not id_token_jwt:
        raise AuthenticationException("Google token exchange did not return an id_token.")

    # 2. Cryptographically verify Google ID token
    google_user = google_oauth.verify_google_id_token(
        id_token_jwt=id_token_jwt, expected_nonce=session_data.get("nonce")
    )

    google_sub = google_user["sub"]
    email = google_user["email"].lower()
    display_name = google_user.get("name") or email.split("@")[0]
    avatar_url = google_user.get("picture")

    # 3. Match Google account to ORBIT user
    # Check 1: User with matching google_id
    stmt = select(User).where(User.google_id == google_sub)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise AuthenticationException("This account is suspended or inactive.")
        user.last_seen_at = utc_now()
        if avatar_url and not user.avatar_url:
            user.avatar_url = avatar_url
        await db.commit()
    else:
        # Check 2: User with matching email but no linked Google sub
        stmt_email = select(User).where(User.email == email)
        res_email = await db.execute(stmt_email)
        existing_email_user = res_email.scalar_one_or_none()

        if existing_email_user:
            # Prevent silent account hijacking. Require password verification to link.
            link_token = google_oauth.create_account_link_token(google_sub=google_sub, email=email)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "ACCOUNT_LINK_REQUIRED",
                    "message": "An account with this email already exists. Verify your password to link your Google account.",
                    "link_token": link_token,
                    "email": email,
                },
            )

        # Check 3: Provision new user with least-privileged role (EMPLOYEE)
        user = User(
            email=email,
            google_id=google_sub,
            display_name=display_name,
            avatar_url=avatar_url,
            role=Role.EMPLOYEE.value,
            timezone="Asia/Kolkata",
            is_active=True,
            last_seen_at=utc_now(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # 4. Issue standard ORBIT JWT
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


@router.post("/google/link", status_code=status.HTTP_200_OK)
async def link_google_account(
    payload: GoogleAccountLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verifies existing account password and links Google sub to existing user identity."""
    link_data = google_oauth.verify_account_link_token(payload.link_token)
    google_sub = link_data.get("sub")
    email = link_data.get("email")

    if not google_sub or not email:
        raise AuthenticationException("Invalid link token payload.")

    stmt = select(User).where(User.email == email)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise AuthenticationException("Unable to link account.")

    if not verify_password(payload.password, user.hashed_password):
        raise AuthenticationException("Invalid password. Account linking failed.")

    if not user.is_active:
        raise AuthenticationException("Account is suspended or inactive.")

    # Securely link the verified Google sub
    user.google_id = google_sub
    user.last_seen_at = utc_now()
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


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Clears authentication cookies on logout."""
    response.delete_cookie(key="orbit_oauth_state", path="/")
    return api_response(data={"message": "Logged out successfully."})


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_session(current_user: User = Depends(get_current_user)):
    """Swap a still-valid token for a fresh one, so an active session does not run out mid-work."""
    token = create_access_token(
        data={"sub": str(current_user.id), "email": current_user.email, "role": current_user.role}
    )
    token_data = TokenResponseData(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserSummary.model_validate(current_user),
    )
    return api_response(data=token_data.model_dump())


@router.get("/me", status_code=status.HTTP_200_OK)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Return profile details of the authenticated caller."""
    user_summary = UserSummary.model_validate(current_user)
    return api_response(data=user_summary.model_dump())
