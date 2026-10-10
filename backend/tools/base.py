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


async def resolve_user_reference(db: AsyncSession, name: str) -> tuple[Optional[Any], Optional[str]]:
    """Resolve a spoken name to exactly one active user.

    Returns ``(user, None)`` for a single clear match, ``(None, message)`` when the
    name is unknown or ambiguous so the agent can ask rather than guess.
    """
    from crud import users as user_crud

    matches = await user_crud.find_users_by_name(db, name)
    if not matches:
        return None, f"I could not find a team member matching '{name}'."

    def label(user: Any) -> str:
        return f"{user.display_name} ({user.email})"

    clean = name.strip().lower()
    exact = [
        u for u in matches
        if clean in (u.display_name.lower(), u.email.lower())
    ]
    if len(exact) == 1:
        return exact[0], None
    first_name_hits = [u for u in matches if u.display_name.split(" ")[0].lower() == clean]
    if len(matches) == 1:
        return matches[0], None
    if len(first_name_hits) == 1:
        return first_name_hits[0], None
    options = ", ".join(label(u) for u in matches[:5])
    return None, f"More than one person matches '{name}': {options}. Which one did you mean?"
