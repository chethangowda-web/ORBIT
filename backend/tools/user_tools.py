"""
User & Team Agent Tools
LangChain-compatible tools for resolving users and team workload.
"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from crud import tasks as task_crud
from crud import users as user_crud
from schemas.user import UserPublic
from tools.base import ToolResult, get_tool_session, tool_error, tool_success


class GetUserByNameInput(BaseModel):
    """Input for looking up users by name or email."""

    name: str = Field(..., description="Full or partial name or email of the user to look up")


class GetAllUsersInput(BaseModel):
    """Input for retrieving all users."""

    limit: int = Field(default=100, description="Maximum number of users to retrieve")


@tool(args_schema=GetUserByNameInput)
async def get_user_by_name(name: str) -> ToolResult:
    """Find a user by full or partial name or email address."""
    try:
        async with get_tool_session() as db:
            users = await user_crud.get_all_users(db=db, q=name, limit=10)

        if not users:
            return tool_error(f"No active user found matching '{name}'")

        user_data = [UserPublic.model_validate(u).model_dump() for u in users]
        return tool_success(data=user_data, count=len(user_data))
    except Exception as e:
        return tool_error(f"Failed to lookup user '{name}': {str(e)}")


@tool(args_schema=GetAllUsersInput)
async def get_all_users(limit: int = 100) -> ToolResult:
    """Retrieve all active registered users in the organization."""
    try:
        async with get_tool_session() as db:
            users = await user_crud.get_all_users(db=db, is_active=True, limit=limit)

        user_data = [UserPublic.model_validate(u).model_dump() for u in users]
        return tool_success(data=user_data, count=len(user_data))
    except Exception as e:
        return tool_error(f"Failed to list users: {str(e)}")


@tool
async def get_team_workload() -> ToolResult:
    """Get the current task workload distribution and completion rates across all team members."""
    try:
        async with get_tool_session() as db:
            workloads = await task_crud.get_team_workload(db=db)

        workload_data = [w.model_dump() for w in workloads]
        return tool_success(data=workload_data, count=len(workload_data))
    except Exception as e:
        return tool_error(f"Failed to calculate team workload: {str(e)}")
