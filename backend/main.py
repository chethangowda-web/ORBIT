"""
ORBIT: Multi-Agent AI Task Management System
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.health import router as health_router
from config import settings
from exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown procedures."""
    # Startup: could verify DB connection or run auto-migrations if configured
    yield
    # Shutdown: clean up resources


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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router (/api)
api_router = APIRouter(prefix=settings.API_V1_PREFIX)
api_router.include_router(health_router)
api_router.include_router(auth_router)

app.include_router(api_router)


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
