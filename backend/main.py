"""
ORBIT: Multi-Agent AI Task Management System
FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

app = FastAPI(
    title="ORBIT - Multi-Agent AI Task Management System",
    description="Intelligent multi-agent task management system with Google Chat integration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
async def root() -> Dict[str, Any]:
    """Root endpoint returning basic service status."""
    return {
        "status": "ok",
        "app": "ORBIT",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["General"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for container probes."""
    return {
        "status": "healthy",
        "service": "orbit-backend",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
