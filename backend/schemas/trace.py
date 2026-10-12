"""Pydantic schemas for Agent Execution Traces (Observability Layer)."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentExecutionTraceRead(BaseModel):
    """Safe, structured representation of an agent execution trace."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: str
    user_id: uuid.UUID
    thread_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    active_agent: Optional[str] = None
    agents_invoked: List[str] = Field(default_factory=list)
    tool_calls_made: List[str] = Field(default_factory=list)
    node_durations_ms: Dict[str, float] = Field(default_factory=dict)
    total_duration_ms: float = 0.0
    classifier: Optional[str] = None  # llm | rules | flow
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "SUCCESS"  # SUCCESS | FAILURE | TIMEOUT | NEEDS_CONFIRMATION
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: datetime
    created_at: datetime

    @field_validator("steps", mode="before")
    @classmethod
    def _steps_default(cls, value: Any) -> Any:
        return value or []


class TraceListResponse(BaseModel):
    """Paginated list of execution traces."""

    items: List[AgentExecutionTraceRead]
    total: int
