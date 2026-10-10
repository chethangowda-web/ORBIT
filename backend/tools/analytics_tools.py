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
    viewer_id: Optional[str] = Field(
        None, description="User asking; employees only see stats for tasks they are assigned to or created"
    )


@tool(args_schema=GetTaskStatsInput)
async def get_task_stats(
    user_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    viewer_id: Optional[str] = None,
) -> ToolResult:
    """Retrieve comprehensive task metrics including totals, completion rate, overdue count, and priority distributions."""
    try:
        parsed_user_id = uuid.UUID(user_id) if user_id else None
        async with get_tool_session() as db:
            involved = None
            if viewer_id is not None:
                from auth.rbac import Role
                from crud import users as user_crud

                viewer = await user_crud.get_user_by_id(db, uuid.UUID(str(viewer_id)))
                if not viewer:
                    return tool_error("Permission denied: unknown user.")
                if Role.from_str(viewer.role) == Role.EMPLOYEE:
                    involved, parsed_user_id = viewer.id, None
            stats = await task_crud.get_task_stats(
                db=db,
                user_id=parsed_user_id,
                date_from=date_from,
                date_to=date_to,
                involved_user_id=involved,
            )

        return tool_success(data=stats.model_dump())
    except Exception as e:
        return tool_error(f"Failed to calculate task statistics: {str(e)}")
