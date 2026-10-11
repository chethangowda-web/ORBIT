"""Server-Sent Events stream that tells dashboards when to refetch."""

import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from auth.jwt import decode_access_token
from db.models import User
from db.session import async_session_factory
from dependencies import security
from exceptions import AuthenticationException
from services.events import MAX_STREAM_SECONDS, event_stream, hub

router = APIRouter(prefix="/events", tags=["Live updates"])


async def authenticate_stream(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[uuid.UUID, float]:
    """Same checks as get_current_user, but the database session is released immediately:
    a stream stays open for hours and must not pin a pooled connection."""
    if not credentials:
        raise AuthenticationException("Authorization header is missing")
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(str((payload or {}).get("sub")))
    except ValueError:
        raise AuthenticationException("Invalid or expired token")
    async with async_session_factory() as db:
        active = (await db.execute(select(User.id).where(User.id == user_id, User.is_active.is_(True)))).scalar_one_or_none()
    if active is None:
        raise AuthenticationException("User not found or account is deactivated")
    # Seconds this stream may live: its maximum, or until the token expires if that comes first.
    lifetime = float(MAX_STREAM_SECONDS)
    expires = (payload or {}).get("exp")
    if isinstance(expires, (int, float)):
        lifetime = max(1.0, min(lifetime, expires - time.time()))
    return user_id, lifetime


@router.get("/stream", summary="Live change notifications (SSE)")
async def stream(auth: tuple[uuid.UUID, float] = Depends(authenticate_stream)):
    """Frames carry only `{topic, task_id}`; the client refetches through the authorised REST API.
    The stream closes after at most 30 minutes (or at token expiry); the browser reconnects, which
    re-checks the token and the account."""
    user_id, lifetime = auth
    queue = hub.subscribe(owner=str(user_id))
    if queue is None:
        return JSONResponse(
            status_code=503,
            content={"success": False, "data": None, "error": "Too many live connections", "meta": None},
            headers={"Retry-After": "30"},
        )
    return StreamingResponse(
        event_stream(queue, max_seconds=lifetime),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
