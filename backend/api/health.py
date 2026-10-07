"""
ORBIT Health and Status Endpoints
Checks connectivity for database, cache, and system components.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from config import settings
from db.session import get_db
from schemas.common import api_response

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
    except Exception as e:
        health_data["database"] = f"disconnected: {str(e)}"
        health_data["status"] = "degraded"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
        health_data["redis"] = "connected"
    except Exception:
        health_data["redis"] = "disconnected (redis offline)"
        if health_data["status"] == "healthy":
            health_data["status"] = "partially_degraded"

    return api_response(data=health_data)
