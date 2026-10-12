"""Intent enumeration and structured extraction models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Intent(str, Enum):
    """Supported user intent categories for agent routing."""

    CREATE_TASK = "CREATE_TASK"
    UPDATE_TASK = "UPDATE_TASK"
    DELETE_TASK = "DELETE_TASK"
    COMPLETE_TASK = "COMPLETE_TASK"
    GET_MY_TASKS = "GET_MY_TASKS"
    GET_OVERDUE_TASKS = "GET_OVERDUE_TASKS"
    SEARCH_TASKS = "SEARCH_TASKS"
    GET_TASK_DETAIL = "GET_TASK_DETAIL"
    PLAN_DAY = "PLAN_DAY"
    GET_RECOMMENDATIONS = "GET_RECOMMENDATIONS"
    HELP = "HELP"
    GREETING = "GREETING"
    MULTI_STEP = "MULTI_STEP"
    UNKNOWN = "UNKNOWN"


class TaskContextExtraction(BaseModel):
    """Extracted task parameters and entities from user input."""

    title: Optional[str] = Field(None, description="Task title extracted from user input")
    assignee_name: Optional[str] = Field(None, description="Assignee name mentioned by user")
    priority: Optional[str] = Field(None, description="Priority: LOW, MEDIUM, HIGH, or CRITICAL")
    due_date: Optional[str] = Field(None, description="Resolved ISO due date string if recognized")
    due_date_relative: Optional[str] = Field(None, description="Relative due date text, e.g. 'Friday', 'tomorrow'")
    task_id: Optional[str] = Field(None, description="Specific task ID/UUID if referenced directly")
    title_hint: Optional[str] = Field(None, description="Search query or keyword hint for task lookup")
    status: Optional[str] = Field(None, description="Task status filter or update value")
    description: Optional[str] = Field(None, description="Task description or notes")


class IntentClassificationResult(BaseModel):
    """Structured LLM output for supervisor classification."""

    intent: Intent = Field(default=Intent.UNKNOWN, description="Classified intent")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    task_context: TaskContextExtraction = Field(default_factory=TaskContextExtraction, description="Extracted task entities")
    explanation: Optional[str] = Field(None, description="Brief rationale for intent classification")
