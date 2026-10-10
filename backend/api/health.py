"""
ORBIT Health and Status Endpoints
Checks connectivity for database, cache, and system components.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from config import settings
from db.session import get_db
from schemas.common import api_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_status(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check checking Database and Redis services."""
    health_data = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown",
    }

    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        health_data["database"] = "connected"
    except Exception as exc:
        # Details stay in the server log: this endpoint is public.
        logger.error("Health check: database unreachable: %s", exc)
        health_data["database"] = "disconnected"
        health_data["status"] = "degraded"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        health_data["redis"] = "connected"
    except Exception as exc:
        logger.warning("Health check: redis unreachable: %s", exc)
        health_data["redis"] = "disconnected"
        if health_data["status"] == "healthy":
            health_data["status"] = "partially_degraded"

    # Check Checkpointer Status
    from agents.memory_agent import get_checkpointer_status
    cp_status = await get_checkpointer_status()
    health_data["checkpoint"] = cp_status
    if not cp_status.get("is_durable") and getattr(settings, "ENVIRONMENT", "development") == "production":
        health_data["status"] = "degraded"

    return api_response(data=health_data)
