"""
ORBIT: Multi-Agent AI Task Management System
FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict
import time

from fastapi import APIRouter, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from config import settings as _boot_settings

logging.basicConfig(
    level=getattr(logging, _boot_settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


from api.admin import router as admin_router
from api.analytics import router as analytics_router
from api.auth import router as auth_router
from api.events import router as events_router
from api.health import router as health_router
from api.planning import router as planning_router
from api.tasks import router as tasks_router
from api.users import router as users_router
from api.webhook import router as webhook_router
from config import settings
from exceptions import register_exception_handlers
from metrics import record_http, render as render_metrics
from agents.memory_agent import close_checkpointer, init_checkpointer
from scheduler.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown procedures."""
    # 1. Initialize Redis / durable checkpointer
    try:
        await init_checkpointer()
    except Exception as exc:
        if settings.ENVIRONMENT == "production":
            raise
    
    # 2. Start scheduler if enabled
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
        
    yield
    
    # 3. Shutdown procedures
    if settings.SCHEDULER_ENABLED:
        stop_scheduler()
    await close_checkpointer()


app = FastAPI(
    title=f"{settings.APP_NAME} - Multi-Agent AI Task Management System",
    description="Intelligent multi-agent task management system with Google Chat integration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Exception handlers
register_exception_handlers(app)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    """Count and time every request, labelled by route template (never the raw URL)."""
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"
        record_http(request.method, path, status_code, time.perf_counter() - started)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX.strip() or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-OAuth-State"],
)

# API Router (/api)
api_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tasks_router)
api_router.include_router(users_router)
api_router.include_router(analytics_router)
api_router.include_router(webhook_router)
api_router.include_router(admin_router)
api_router.include_router(events_router)
api_router.include_router(planning_router)

app.include_router(api_router)

# Legacy aliases for bots configured before the canonical /api/chat/webhook URL.
# Hidden from the schema; new setups should use /api/chat/webhook.
from api.webhook import google_chat_webhook

for _legacy_path in ("/webhook", "/api/cha"):
    app.add_api_route(_legacy_path, google_chat_webhook, methods=["POST"], include_in_schema=False)


@app.get("/", tags=["General"])
async def root() -> Dict[str, Any]:
    """Root endpoint returning basic service status."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint(authorization: str | None = Header(None)) -> Response:
    """Prometheus scrape endpoint: disabled unless METRICS_ENABLED, token-protected if METRICS_TOKEN is set."""
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    if settings.METRICS_TOKEN and authorization != f"Bearer {settings.METRICS_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid or missing metrics token")
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/health", tags=["General"])
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint for container probes."""
    return {
        "status": "healthy",
        "service": "orbit-backend",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
