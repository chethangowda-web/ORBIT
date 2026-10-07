"""Memory Agent: Checkpointer provider and conversation coreference resolution."""

import re
from typing import Any, Optional
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AgentState

# Global in-memory checkpointer fallback
_memory_saver = MemorySaver()


def get_checkpointer():
    """Returns the configured LangGraph checkpointer."""
    return _memory_saver


def make_thread_id(space_id: str, user_id: str) -> str:
    """Generates standard thread ID: space_id:user_id."""
    return f"{space_id}:{user_id}"


def extract_task_id_from_text(text: str) -> Optional[str]:
    """Extracts task UUID or Task #ID from message text."""
    # Look for UUID pattern
    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text,
    )
    if uuid_match:
        return uuid_match.group(0)
    # Look for Task #ID pattern
    num_match = re.search(r"Task\s*#?\s*([0-9a-fA-F\-]+)", text, re.IGNORECASE)
    if num_match:
        return num_match.group(1)
    return None


def resolve_references(raw_message: str, messages: list[BaseMessage]) -> Optional[str]:
    """Resolves 'it', 'that task', 'the task' to the most recently mentioned task ID in conversation history."""
    msg = raw_message.lower()
    pronouns = ["it", "that task", "the task", "this task", "same task"]
    if not any(p in msg for p in pronouns):
        return None

    # Search backwards through AI messages
    for m in reversed(messages):
        if isinstance(m, AIMessage) or hasattr(m, "content"):
            content = str(m.content)
            found_id = extract_task_id_from_text(content)
            if found_id:
                return found_id
    return None
