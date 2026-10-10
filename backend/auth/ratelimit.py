"""Sliding-window login rate limiter.

Uses Redis when reachable so limits hold across workers, and degrades to a
per-process in-memory window when Redis is down. The key combines client IP and
the (lowercased) email so one attacker cannot lock out everyone, and one account
cannot be hammered from a single address.
"""

import logging
import time
from collections import defaultdict, deque

import redis.asyncio as aioredis
from fastapi import Request

from config import settings
from exceptions import OrbitException

logger = logging.getLogger(__name__)

_memory_hits: dict[str, deque[float]] = defaultdict(deque)
_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            )
        except Exception as exc:  # malformed URL and similar
            logger.warning("Rate limiter cannot build Redis client: %s", exc)
            return None
    return _redis_client


def client_ip(request: Request) -> str:
    """Best-effort client address; honours the first X-Forwarded-For hop."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _memory_prune(key: str, window: int) -> deque[float]:
    now = time.monotonic()
    hits = _memory_hits[key]
    while hits and now - hits[0] > window:
        hits.popleft()
    return hits


def _login_key(request: Request, email: str) -> str:
    return f"login:{client_ip(request)}:{email.strip().lower()}"


async def enforce_login_rate_limit(request: Request, email: str) -> None:
    """Raise 429 once an IP+email pair has used up its failed-attempt budget."""
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    key = _login_key(request, email)
    count = 0
    client = _get_redis()
    if client is not None:
        try:
            raw = await client.get(f"orbit:ratelimit:{key}")
            count = int(raw) if raw else 0
        except Exception as exc:
            logger.warning("Rate limiter falling back to memory: %s", exc)
            client = None
    if client is None:
        count = len(_memory_prune(key, window))
    if count >= settings.LOGIN_RATE_LIMIT_ATTEMPTS:
        raise OrbitException(
            "Too many sign-in attempts. Please wait a few minutes and try again.",
            status_code=429,
        )


async def record_login_failure(request: Request, email: str) -> None:
    """Count one failed sign-in for this IP+email pair."""
    window = settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    key = _login_key(request, email)
    client = _get_redis()
    if client is not None:
        try:
            redis_key = f"orbit:ratelimit:{key}"
            if await client.incr(redis_key) == 1:
                await client.expire(redis_key, window)
            return
        except Exception as exc:
            logger.warning("Rate limiter falling back to memory: %s", exc)
    _memory_prune(key, window).append(time.monotonic())


async def clear_login_failures(request: Request, email: str) -> None:
    """Forget failures after a successful sign-in."""
    key = _login_key(request, email)
    _memory_hits.pop(key, None)
    client = _get_redis()
    if client is not None:
        try:
            await client.delete(f"orbit:ratelimit:{key}")
        except Exception as exc:
            logger.warning("Could not clear login failures: %s", exc)


def reset_memory_limits() -> None:
    """Test helper: clear in-process counters."""
    _memory_hits.clear()
