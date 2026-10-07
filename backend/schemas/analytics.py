"""
Analytics and Statistics Pydantic Schemas
"""

from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict
from schemas.user import UserSummary


class DailyCount(BaseModel):
    """Daily aggregated count metric."""

    date: str
    count: int


class TaskStatsResponse(BaseModel):
    """Aggregate statistics for task dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    completion_rate: float = 0.0
    avg_completion_days: float = 0.0
    tasks_by_priority: Dict[str, int] = {}
    tasks_by_status: Dict[str, int] = {}
    tasks_created_per_day: List[DailyCount] = []


class TeamMemberWorkload(BaseModel):
    """Workload distribution for an individual team member."""

    model_config = ConfigDict(from_attributes=True)

    user: UserSummary
    total_tasks: int = 0
    overdue_tasks: int = 0
    high_priority_tasks: int = 0
    completion_rate: float = 0.0
