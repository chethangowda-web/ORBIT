"""ORBIT Google OAuth 2.0 & OpenID Connect Service.

Implements PKCE authorization code exchange, cryptographic state and nonce validation,
and Google ID token verification with safe account provisioning.
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional, Tuple
import urllib.parse

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import httpx
from jose import JWTError, jwt

from config import settings
from exceptions import AuthenticationException, OrbitException


def generate_pkce_pair() -> Tuple[str, str]:
    """Generates PKCE code_verifier and S256 code_challenge."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def create_oauth_session_token(
    state: str, code_verifier: str, nonce: str, expires_minutes: int = 10
) -> str:
    """Signs state, code_verifier, and nonce into a tamper-proof session JWT."""
    now = datetime.now(timezone.utc)
    payload = {
        "state": state,
        "code_verifier": code_verifier,
        "nonce": nonce,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
        "type": "oauth_state",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_oauth_session_token(token: str) -> Dict[str, Any]:
    """Validates the tamper-proof OAuth session token and returns the payload."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "oauth_state":
            raise AuthenticationException("Invalid OAuth state token type")
        return payload
    except JWTError as err:
        raise AuthenticationException(f"OAuth state expired or invalid: {str(err)}")


def build_google_authorization_url(
    state: str, code_challenge: str, nonce: str
) -> str:
    """Constructs the Google OAuth 2.0 authorization URL with PKCE."""
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "nonce": nonce,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"


async def exchange_google_code(code: str, code_verifier: str) -> Dict[str, Any]:
    """Exchanges authorization code and PKCE verifier for Google tokens."""
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            raise AuthenticationException(
                f"Failed to exchange Google authorization code: {response.text}"
            )
        return response.json()


def verify_google_id_token(
    id_token_jwt: str, expected_nonce: Optional[str] = None
) -> Dict[str, Any]:
    """Validates Google ID token signature, issuer, audience, expiry, nonce, and verified email."""
    try:
        # In test environments with mock tokens, allow test validation
        payload = id_token.verify_oauth2_token(
            id_token_jwt,
            google_requests.Request(),
            audience=settings.GOOGLE_OAUTH_CLIENT_ID,
        )

        issuer = payload.get("iss")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise AuthenticationException(f"Invalid Google token issuer: {issuer}")

        if expected_nonce and payload.get("nonce") != expected_nonce:
            raise AuthenticationException("Google ID token nonce does not match")

        if not payload.get("email_verified", False):
            raise AuthenticationException("Google account email is not verified")

        if not payload.get("sub"):
            raise AuthenticationException("Google token missing immutable 'sub' claim")

        return payload
    except ValueError as e:
        raise AuthenticationException(f"Invalid Google ID token: {str(e)}")


def create_account_link_token(google_sub: str, email: str) -> str:
    """Creates a short-lived token allowing account linking upon password verification."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": google_sub,
        "email": email,
        "exp": now + timedelta(minutes=10),
        "iat": now,
        "type": "account_link",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_account_link_token(token: str) -> Dict[str, Any]:
    """Verifies account linking token."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "account_link":
            raise AuthenticationException("Invalid link token type")
        return payload
    except JWTError as err:
        raise AuthenticationException(f"Link token expired or invalid: {str(err)}")
