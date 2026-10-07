"""
Task Pydantic Schemas
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from schemas.user import UserRead


class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskBase(BaseModel):
    """Base task fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[date] = None
    tags: List[str] = Field(default_factory=list)


class TaskCreate(TaskBase):
    """Payload to create a new task."""

    assignee_id: Optional[uuid.UUID] = None


class TaskUpdate(BaseModel):
    """Payload to update an existing task."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    tags: Optional[List[str]] = None


class TaskCompleteRequest(BaseModel):
    """Payload for completing a task."""

    completion_note: Optional[str] = None


class TaskAuditRead(BaseModel):
    """Audit log entry representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    action: str
    changes: Optional[Dict[str, Any]] = None
    source: str
    created_at: datetime
    user: Optional[UserRead] = None


class TaskRead(TaskBase):
    """Full task schema representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: TaskStatus
    assignee_id: Optional[uuid.UUID] = None
    created_by_id: uuid.UUID
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    days_overdue: Optional[int] = None
    assignee: Optional[UserRead] = None
    creator: Optional[UserRead] = None


class TaskDetailRead(TaskRead):
    """Task schema including full audit history."""

    audit_logs: List[TaskAuditRead] = Field(default_factory=list)
