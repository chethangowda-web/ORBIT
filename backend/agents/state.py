"""Agent state definitions for LangGraph multi-agent workflow."""

from typing import Any, Optional, TypedDict
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """Shared state dictionary passed across all nodes in the LangGraph."""

    # === INPUT ===
    user_id: str                          # Internal user UUID string
    google_user_id: str                   # Google Chat user ID
    space_id: str                         # Google Chat space ID
    thread_id: str                        # Conversation thread ID (space_id:user_id)
    raw_message: str                      # Original user message

    # === ROUTING ===
    intent: str                           # Classified intent enum value
    confidence: float                     # Intent classification confidence (0.0 to 1.0)
    classifier: str                       # How the intent was decided: llm | rules | flow
    active_agent: str                     # Which specialist agent is running

    # === CONVERSATION HISTORY ===
    messages: list[BaseMessage]           # Full LangChain message history

    # === EXTRACTED CONTEXT ===
    task_context: dict[str, Any]          # Extracted fields {title, assignee_name, priority, due_date, ...}
    referenced_task_id: Optional[str]     # If user referenced a specific task UUID / ID
    pending_duplicate: Optional[dict[str, Any]]  # A create request held back because the same task exists

    # === CONTROL FLOW ===
    needs_confirmation: bool              # HITL — requires user confirmation
    confirmed: bool                       # User confirmed the action
    pending_confirmation: Optional[dict[str, Any]] # Structured tamper-resistant confirmation details

    # === OUTPUT ===
    response: str                         # Final response text for Google Chat
    response_type: str                    # "text" | "card" | "confirmation_dialog"
    card_data: Optional[dict[str, Any]]   # Google Chat card payload
    tool_calls_made: list[str]            # Audit log of tools called in this run
    actions_summary: list[str]            # Plain-language list of what the tool-using agent changed
    agents_invoked: list[str]             # List of agent nodes invoked in order
    node_durations_ms: dict[str, float]   # Milliseconds spent in each node
    trace_metadata: Optional[dict[str, Any]] # Observability trace record

    # === ERROR ===
    error: Optional[str]                  # Error message if agent failed
    error_code: Optional[str]             # Standardized error code
    retry_count: int                      # Number of retries attempted

