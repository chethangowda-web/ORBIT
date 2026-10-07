"""
ORBIT Agent Tool Base Definitions
Provides standard ToolResult return structure and safe execution helpers with ContextVar session binding.
"""

from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Any, AsyncGenerator, Dict, Optional, TypedDict
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import async_session_factory

# Context variable holding the active session for tool executions
current_tool_session: ContextVar[Optional[AsyncSession]] = ContextVar("current_tool_session", default=None)


@asynccontextmanager
async def get_tool_session(provided_session: Optional[AsyncSession] = None) -> AsyncGenerator[AsyncSession, None]:
    """Yield active session or open a new session."""
    active_session = provided_session or current_tool_session.get()
    if active_session is not None:
        token = current_tool_session.set(active_session)
        try:
            yield active_session
        finally:
            current_tool_session.reset(token)
    else:
        async with async_session_factory() as session:
            token = current_tool_session.set(session)
            try:
                yield session
            finally:
                current_tool_session.reset(token)


class ToolResult(TypedDict):
    """Standard dictionary envelope returned by all agent tools."""

    success: bool
    data: Any
    error: Optional[str]
    count: Optional[int]


def tool_success(data: Any = None, count: Optional[int] = None) -> ToolResult:
    """Build a successful tool response payload."""
    res_count = count if count is not None else (len(data) if isinstance(data, list) else None)
    return {
        "success": True,
        "data": data,
        "error": None,
        "count": res_count,
    }


def tool_error(error_msg: str, data: Any = None) -> ToolResult:
    """Build an error tool response payload (agents receive error safely without throwing)."""
    return {
        "success": False,
        "data": data,
        "error": error_msg,
        "count": None,
    }
