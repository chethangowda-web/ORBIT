"""Google Chat event schemas for webhook payloads and card actions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class GoogleChatUser(BaseModel):
    """Google Chat user profile payload."""

    name: str = Field(..., description="Google Chat user ID format: users/1234567")
    displayName: Optional[str] = Field(None, description="User's display name")
    email: Optional[str] = Field(None, description="User's email address")
    type: Optional[str] = Field(None, description="HUMAN or BOT")


class GoogleChatSpace(BaseModel):
    """Google Chat space payload."""

    name: str = Field(default="spaces/default", description="Space identifier format: spaces/AAA123")
    type: Optional[str] = Field(None, description="ROOM, DM, or SPACE")
    displayName: Optional[str] = Field(None, description="Space display name")


class GoogleChatMessage(BaseModel):
    """Google Chat message payload."""

    name: Optional[str] = Field(None, description="Message resource name")
    text: str = Field(default="", description="Raw text of the user message")
    thread: Optional[Dict[str, Any]] = Field(None, description="Thread info")
    argumentText: Optional[str] = Field(None, description="Text after a slash command or mention")
    slashCommand: Optional[Dict[str, Any]] = Field(None, description="Present when the message is a slash command: {commandId}")


class CardAction(BaseModel):
    """Action payload for interactive button clicks."""

    actionMethodName: Optional[str] = Field(None, description="Name of action method, e.g. confirm_delete")
    parameters: Optional[List[Dict[str, str]]] = Field(None, description="Action parameter key-value pairs")


class GoogleChatEvent(BaseModel):
    """Incoming Google Chat webhook event schema."""

    type: str = Field(default="MESSAGE", description="MESSAGE, CARD_CLICKED, ADDED_TO_SPACE, REMOVED_FROM_SPACE, APP_HOME")
    eventTime: Optional[str] = Field(None, description="ISO timestamp")
    space: GoogleChatSpace = Field(default_factory=lambda: GoogleChatSpace(name="spaces/default", type="DM"), description="Space where event occurred")
    user: Optional[GoogleChatUser] = Field(None, description="Sender profile")
    message: Optional[GoogleChatMessage] = Field(None, description="Message details if type is MESSAGE")
    action: Optional[CardAction] = Field(None, description="Action details if type is CARD_CLICKED")
    commonEventObject: Optional[Dict[str, Any]] = Field(None, description="Google Workspace Add-on common event object")


# ============================================================================
# AI Command Center Web Query Schemas
# ============================================================================


class ChatQueryRequest(BaseModel):
    """Payload for querying ORBIT via the Web Command Center."""

    message: str = Field(..., min_length=1, max_length=2000, description="Natural language prompt or command")
    thread_id: Optional[str] = Field(None, max_length=100, description="Conversation thread identifier")
    confirmed: bool = Field(False, description="Flag indicating user approved a pending confirmation action")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Message cannot be empty or whitespace only")
        return trimmed


class ChatExecutionMetadata(BaseModel):
    """Execution metadata safely returned to client."""

    request_id: Optional[str] = None
    active_agent: Optional[str] = None
    agents_invoked: List[str] = Field(default_factory=list)
    intent: Optional[str] = None
    confidence: Optional[float] = None
    tool_calls_made: List[str] = Field(default_factory=list)
    node_durations_ms: Dict[str, float] = Field(default_factory=dict)
    total_duration_ms: float = 0.0
    status: str = "SUCCESS"


class ReferencedTaskSummary(BaseModel):
    """Summarized task referenced or modified during the query."""

    id: str
    title: str
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    assignee_name: Optional[str] = None


class ChatQueryResponse(BaseModel):
    """Structured response from LangGraph multi-agent execution."""

    response: str
    thread_id: str
    message_id: str
    needs_confirmation: bool = False
    referenced_task_id: Optional[str] = None
    referenced_tasks: List[ReferencedTaskSummary] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    metadata: ChatExecutionMetadata = Field(default_factory=ChatExecutionMetadata)
