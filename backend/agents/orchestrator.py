"""Multi-Agent Orchestrator: Invokes LangGraph workflow with streaming observability, timing, and trace persistence."""

import asyncio
from datetime import datetime, timezone
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from agents.graph import get_compiled_graph
from agents.memory_agent import make_thread_id
from agents.state import AgentState
from config import settings
from crud.traces import create_trace
from metrics import record_agent_run
from tools.base import get_tool_session

logger = logging.getLogger(__name__)


async def process_message(
    user_id: str,
    space_id: str,
    message: str,
    thread_id: Optional[str] = None,
    google_user_id: Optional[str] = None,
    confirmed: bool = False,
    session: Optional[AsyncSession] = None,
    timeout_seconds: Optional[float] = None,
) -> AgentState:
    """Processes a user message through the LangGraph multi-agent pipeline with real-time execution tracing."""
    timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.AGENT_TIMEOUT_SECONDS
    request_id = str(uuid.uuid4())
    tid = thread_id or make_thread_id(space_id, user_id)
    started_at = datetime.now(timezone.utc)
    t_start = time.perf_counter()

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

    agents_invoked: List[str] = []
    node_durations_ms: Dict[str, float] = {}
    steps: List[Dict[str, Any]] = []
    accumulated_state: Dict[str, Any] = dict(initial_state)

    async def _run_graph_stream() -> Dict[str, Any]:
        nonlocal accumulated_state
        graph = get_compiled_graph()
        last_step_time = time.perf_counter()
        async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, updates in chunk.items():
                t_now = time.perf_counter()
                node_delta_ms = round((t_now - last_step_time) * 1000, 2)
                last_step_time = t_now

                if node_name not in agents_invoked:
                    agents_invoked.append(node_name)
                # Compute individual elapsed time for node (aggregate if node is revisited in graph loop)
                node_durations_ms[node_name] = round(node_durations_ms.get(node_name, 0.0) + node_delta_ms, 2)
                step: Dict[str, Any] = {"node": node_name, "duration_ms": node_delta_ms}
                if isinstance(updates, dict):
                    # Tools are attributed to the node that added them to the running list.
                    known = accumulated_state.get("tool_calls_made") or []
                    now = updates.get("tool_calls_made") or []
                    new_tools = list(now[len(known):]) if len(now) >= len(known) else list(now)
                    if new_tools:
                        step["tools"] = new_tools
                    if node_name == "supervisor":
                        step["intent"] = updates.get("intent")
                        step["confidence"] = updates.get("confidence")
                        step["classifier"] = updates.get("classifier")
                    elif updates.get("needs_confirmation"):
                        step["awaiting_confirmation"] = True
                    if updates.get("actions_summary"):
                        step["actions"] = list(updates["actions_summary"])
                    accumulated_state.update(updates)
                steps.append(step)
        return accumulated_state

    try:
        async with get_tool_session(session):
            result = await asyncio.wait_for(
                _run_graph_stream(),
                timeout=timeout_seconds,
            )
            completed_at = datetime.now(timezone.utc)
            total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

            needs_conf = bool(result.get("needs_confirmation", False))
            status = "NEEDS_CONFIRMATION" if needs_conf else "SUCCESS"

            trace_dict = {
                "request_id": request_id,
                "thread_id": tid,
                "intent": result.get("intent", "UNKNOWN"),
                "confidence": result.get("confidence"),
                "active_agent": result.get("active_agent", agents_invoked[-1] if agents_invoked else "supervisor"),
                "agents_invoked": agents_invoked,
                "tool_calls_made": result.get("tool_calls_made", []),
                "node_durations_ms": node_durations_ms,
                "total_duration_ms": total_duration_ms,
                "classifier": result.get("classifier"),
                "steps": steps,
                "status": status,
                "error_code": None,
                "error_message": None,
                "started_at": started_at,
                "completed_at": completed_at,
            }
            record_agent_run(trace_dict)

            # Persist trace if db session and valid UUID
            if session:
                try:
                    user_uuid = uuid.UUID(user_id)
                    await create_trace(session, {**trace_dict, "user_id": user_uuid})
                except Exception as trace_err:
                    logger.warning("Failed to persist execution trace: %s", trace_err)

            result["agents_invoked"] = agents_invoked
            result["node_durations_ms"] = node_durations_ms
            result["trace_metadata"] = trace_dict
            return result  # type: ignore

    except asyncio.TimeoutError:
        completed_at = datetime.now(timezone.utc)
        total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.error("Agent execution timed out for thread %s", tid)

        trace_dict = {
            "request_id": request_id,
            "thread_id": tid,
            "intent": accumulated_state.get("intent", "UNKNOWN"),
            "confidence": accumulated_state.get("confidence"),
            "active_agent": "supervisor",
            "agents_invoked": agents_invoked,
            "tool_calls_made": accumulated_state.get("tool_calls_made", []),
            "node_durations_ms": node_durations_ms,
            "total_duration_ms": total_duration_ms,
            "classifier": accumulated_state.get("classifier"),
            "steps": steps,
            "status": "TIMEOUT",
            "error_code": "AGENT_TIMEOUT",
            "error_message": "Agent execution timed out",
            "started_at": started_at,
            "completed_at": completed_at,
        }
        record_agent_run(trace_dict)

        if session:
            try:
                user_uuid = uuid.UUID(user_id)
                await create_trace(session, {**trace_dict, "user_id": user_uuid})
            except Exception as trace_err:
                logger.warning("Failed to persist timeout trace: %s", trace_err)

        return {
            "user_id": user_id,
            "thread_id": tid,
            "raw_message": message,
            "active_agent": "supervisor",
            "agents_invoked": agents_invoked,
            "intent": "UNKNOWN",
            "needs_confirmation": False,
            "response": "⚠️ That took longer than expected. Please try again in a moment.",
            "response_type": "text",
            "tool_calls_made": accumulated_state.get("tool_calls_made", []),
            "node_durations_ms": node_durations_ms,
            "trace_metadata": trace_dict,
            "error": "Agent execution timed out",
            "error_code": "AGENT_TIMEOUT",
        }

    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.error("Agent execution failed for thread %s: %s", tid, exc)

        trace_dict = {
            "request_id": request_id,
            "thread_id": tid,
            "intent": accumulated_state.get("intent", "UNKNOWN"),
            "confidence": accumulated_state.get("confidence"),
            "active_agent": "supervisor",
            "agents_invoked": agents_invoked,
            "tool_calls_made": accumulated_state.get("tool_calls_made", []),
            "node_durations_ms": node_durations_ms,
            "total_duration_ms": total_duration_ms,
            "classifier": accumulated_state.get("classifier"),
            "steps": steps,
            "status": "FAILURE",
            "error_code": "AGENT_EXECUTION_ERROR",
            "error_message": str(exc)[:500],
            "started_at": started_at,
            "completed_at": completed_at,
        }
        record_agent_run(trace_dict)

        if session:
            try:
                user_uuid = uuid.UUID(user_id)
                await create_trace(session, {**trace_dict, "user_id": user_uuid})
            except Exception as trace_err:
                logger.warning("Failed to persist error trace: %s", trace_err)

        return {
            "user_id": user_id,
            "thread_id": tid,
            "raw_message": message,
            "active_agent": "supervisor",
            "agents_invoked": agents_invoked,
            "intent": "UNKNOWN",
            "needs_confirmation": False,
            "response": "❌ Something went wrong while handling that request. Please try again in a moment.",
            "response_type": "text",
            "tool_calls_made": accumulated_state.get("tool_calls_made", []),
            "node_durations_ms": node_durations_ms,
            "trace_metadata": trace_dict,
            "error": str(exc),
            "error_code": "AGENT_EXECUTION_ERROR",
        }
