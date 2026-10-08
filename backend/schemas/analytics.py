"""
Analytics and Statistics Pydantic Schemas
"""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class DailyCount(BaseModel):
    """Daily aggregated count metric."""

    date: str
    count: int


class TaskStatsResponse(BaseModel):
    """Aggregate statistics for task dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0
    overdue_tasks: int = 0
    completion_rate: float = 0.0
    avg_completion_days: float = 0.0
    # Aliased for frontend compatibility
    by_priority: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    tasks_by_priority: Dict[str, int] = {}
    tasks_by_status: Dict[str, int] = {}
    tasks_created_per_day: List[DailyCount] = []


class TeamMemberWorkload(BaseModel):
    """Workload distribution for an individual team member — flattened for frontend."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    display_name: str
    email: str
    role: str
    assigned_tasks: int = 0
    completed_tasks: int = 0
    overdue_tasks: int = 0
    high_priority_tasks: int = 0
    completion_rate: float = 0.0
