"""CRUD operations for AgentExecutionTrace entities."""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentExecutionTrace


async def create_trace(
    db: AsyncSession,
    trace_data: Dict[str, Any],
) -> AgentExecutionTrace:
    """Persist an agent execution trace to the database."""
    trace = AgentExecutionTrace(**trace_data)
    db.add(trace)
    await db.commit()
    await db.refresh(trace)
    return trace


async def list_user_traces(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[AgentExecutionTrace], int]:
    """Retrieve execution traces scoped strictly to the authenticated user."""
    query = (
        select(AgentExecutionTrace)
        .where(AgentExecutionTrace.user_id == user_id)
        .order_by(desc(AgentExecutionTrace.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    traces = list(result.scalars().all())

    # Count total for user
    count_query = select(AgentExecutionTrace).where(AgentExecutionTrace.user_id == user_id)
    count_res = await db.execute(count_query)
    total = len(count_res.scalars().all())

    return traces, total


async def get_user_trace(
    db: AsyncSession,
    user_id: uuid.UUID,
    trace_id: uuid.UUID,
) -> Optional[AgentExecutionTrace]:
    """Retrieve a single execution trace ensuring user ownership."""
    query = (
        select(AgentExecutionTrace)
        .where(
            AgentExecutionTrace.id == trace_id,
            AgentExecutionTrace.user_id == user_id,
        )
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()
