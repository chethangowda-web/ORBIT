"""Agent Orchestrator: Entry point for executing the LangGraph agent pipeline."""

from typing import Any, Optional
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import agent_graph
from agents.memory_agent import make_thread_id
from agents.state import AgentState
from tools.base import get_tool_session


async def process_message(
    user_id: str,
    space_id: str,
    message: str,
    thread_id: Optional[str] = None,
    google_user_id: Optional[str] = None,
    confirmed: bool = False,
    session: Optional[AsyncSession] = None,
) -> AgentState:
    """Processes a user message through the LangGraph multi-agent pipeline."""
    tid = thread_id or make_thread_id(space_id, user_id)
    initial_state: AgentState = {
        "user_id": user_id,
        "google_user_id": google_user_id or user_id,
        "space_id": space_id,
        "thread_id": tid,
        "raw_message": message,
        "confirmed": confirmed,
        "messages": [HumanMessage(content=message)],
        "tool_calls_made": [],
    }

    config = {
        "configurable": {"thread_id": tid},
        "recursion_limit": 10,
    }

    async with get_tool_session(session):
        result = await agent_graph.ainvoke(initial_state, config=config)  # type: ignore
        return result  # type: ignore
