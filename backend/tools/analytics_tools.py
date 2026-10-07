"""
Analytics & Metrics Agent Tools
LangChain-compatible tools for task and team productivity analytics.
"""

import uuid
from datetime import date
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from crud import tasks as task_crud
from tools.base import ToolResult, get_tool_session, tool_error, tool_success


class GetTaskStatsInput(BaseModel):
    """Input for retrieving aggregate task statistics."""

    user_id: Optional[str] = Field(None, description="UUID of the user to filter metrics for, or None for team-wide")
    date_from: Optional[date] = Field(None, description="Start date for filtering task creation metrics")
    date_to: Optional[date] = Field(None, description="End date for filtering task creation metrics")


@tool(args_schema=GetTaskStatsInput)
async def get_task_stats(
    user_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> ToolResult:
    """Retrieve comprehensive task metrics including totals, completion rate, overdue count, and priority distributions."""
    try:
        parsed_user_id = uuid.UUID(user_id) if user_id else None
        async with get_tool_session() as db:
            stats = await task_crud.get_task_stats(
                db=db, user_id=parsed_user_id, date_from=date_from, date_to=date_to
            )

        return tool_success(data=stats.model_dump())
    except Exception as e:
        return tool_error(f"Failed to calculate task statistics: {str(e)}")
