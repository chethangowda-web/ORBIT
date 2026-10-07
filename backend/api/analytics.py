"""
ORBIT Analytics Endpoints
Provides system-wide and user-level task metric aggregates and team workload distributions.
"""

import uuid
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud import tasks as task_crud
from db.models import User
from db.session import get_db
from dependencies import get_current_user
from schemas.common import api_response

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/stats", status_code=status.HTTP_200_OK)
async def get_task_statistics(
    user_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve aggregate task statistics and metrics."""
    stats = await task_crud.get_task_stats(
        db=db, user_id=user_id, date_from=date_from, date_to=date_to
    )
    return api_response(data=stats.model_dump())


@router.get("/team-workload", status_code=status.HTTP_200_OK)
async def get_team_workload_distribution(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve current task workload and completion metrics across team members."""
    workloads = await task_crud.get_team_workload(db=db)
    return api_response(data=[w.model_dump() for w in workloads])
