"""
Task Pydantic Schemas
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from schemas.user import UserPublic


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


def _clean_title(value: str) -> str:
    """Trim, then insist on something left: "   " used to be stored as "" and then made every
    list that contained the task fail validation on the way out."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("Title cannot be blank.")
    return stripped


class TaskCreate(TaskBase):
    """Payload to create a new task."""

    assignee_id: Optional[uuid.UUID] = None

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        return _clean_title(value)


class TaskUpdate(BaseModel):
    """Payload to update an existing task."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    tags: Optional[List[str]] = None

    @field_validator("title", "status", "priority", "tags")
    @classmethod
    def _not_null(cls, value: Any) -> Any:
        """These columns are NOT NULL: an explicit null is a client error, not a database error
        (or worse, a stored JSON null that breaks every read of the task). description, due_date and
        assignee_id may be null to clear them."""
        if value is None:
            raise ValueError("This field cannot be null.")
        return value

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        return _clean_title(value)


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
    user: Optional[UserPublic] = None


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
    assignee: Optional[UserPublic] = None
    creator: Optional[UserPublic] = None


class TaskDetailRead(TaskRead):
    """Task schema including full audit history."""

    audit_logs: List[TaskAuditRead] = Field(default_factory=list)


class CommentCreate(BaseModel):
    """Payload to add a comment."""

    body: str = Field(..., min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Comment cannot be empty")
        return stripped


class CommentRead(BaseModel):
    """Comment returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    body: str
    created_at: datetime
    author: Optional[UserPublic] = None


class AttachmentRead(BaseModel):
    """Attachment metadata. The stored file name is never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    uploader: Optional[UserPublic] = None


class BulkTaskAction(BaseModel):
    """Apply one action to many tasks at once (max 50)."""

    task_ids: List[uuid.UUID] = Field(..., min_length=1, max_length=50)
    action: Literal["complete", "set_status", "set_priority", "assign", "delete"]
    value: Optional[str] = Field(None, max_length=64, description="Status, priority or assignee id depending on action")

    @model_validator(mode="after")
    def _check_value(self) -> "BulkTaskAction":
        if self.action == "set_status" and self.value not in {s.value for s in TaskStatus}:
            raise ValueError("value must be a valid status for set_status")
        if self.action == "set_priority" and self.value not in {p.value for p in TaskPriority}:
            raise ValueError("value must be a valid priority for set_priority")
        if self.action == "assign" and self.value:
            try:
                uuid.UUID(self.value)
            except ValueError as exc:
                raise ValueError("value must be a user id (or empty to unassign) for assign") from exc
        return self


class BulkFailure(BaseModel):
    id: uuid.UUID
    reason: str


class BulkTaskResult(BaseModel):
    succeeded: List[uuid.UUID]
    failed: List[BulkFailure]
