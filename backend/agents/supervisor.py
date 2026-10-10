"""Supervisor Agent: Intent classification and specialist agent routing."""

from typing import Any
from agents.intents import (
    Intent,
    IntentClassificationResult,
)
from agents.memory_agent import resolve_references
from agents.prompts import SUPERVISOR_PROMPT
from agents.state import AgentState
from services.llm import call_llm, fallback_intent_classifier

ROUTING_MAP: dict[Intent, str] = {
    Intent.CREATE_TASK: "task_agent",
    Intent.UPDATE_TASK: "task_agent",
    Intent.DELETE_TASK: "review_agent",
    Intent.COMPLETE_TASK: "task_agent",
    Intent.GET_MY_TASKS: "task_agent",
    Intent.GET_OVERDUE_TASKS: "recommendation_agent",
    Intent.SEARCH_TASKS: "task_agent",
    Intent.GET_TASK_DETAIL: "task_agent",
    Intent.PLAN_DAY: "planner_agent",
    Intent.GET_RECOMMENDATIONS: "recommendation_agent",
    Intent.HELP: "task_agent",
    Intent.GREETING: "task_agent",
    Intent.UNKNOWN: "task_agent",
}


async def classify_intent(raw_message: str) -> IntentClassificationResult:
    """Classifies user intent using LiteLLM structured output or rule fallback."""
    messages = [
        {"role": "system", "content": SUPERVISOR_PROMPT},
        {"role": "user", "content": raw_message},
    ]
    res = await call_llm(
        messages=messages,
        temperature=0.1,
        response_model=IntentClassificationResult,
    )
    if isinstance(res, IntentClassificationResult):
        return res
    return fallback_intent_classifier(raw_message)


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Classifies intent, resolves coreference, and routes."""
    raw_message = state.get("raw_message", "")
    history = state.get("messages", [])
    confirmed = state.get("confirmed", False)
    needs_conf = state.get("needs_confirmation", False)

    pending = state.get("pending_confirmation")
    msg_clean = raw_message.strip().lower()

    # Handle Cancellation of pending actions
    if (needs_conf or (pending and pending.get("status") == "PENDING")) and msg_clean in ("cancel", "no", "abort", "n", "stop", "nevermind"):
        pending_updated = dict(pending) if pending else {}
        pending_updated["status"] = "CANCELLED"
        return {
            "intent": Intent.UNKNOWN.value,
            "confidence": 1.0,
            "active_agent": "task_agent",
            "task_context": {},
            "referenced_task_id": None,
            "confirmed": False,
            "needs_confirmation": False,
            "pending_confirmation": pending_updated,
            "response": "❌ Action cancelled.",
            "response_type": "text",
            "tool_calls_made": state.get("tool_calls_made", []),
        }

    # Handle Confirmation requests
    is_confirm_attempt = confirmed or (needs_conf and msg_clean in ("yes", "confirm", "proceed", "y", "ok", "true"))

    if is_confirm_attempt:
        target_intent = Intent.DELETE_TASK
        task_context = dict(state.get("task_context") or {})
        ref_id = (pending.get("task_id") if pending else None) or state.get("referenced_task_id")
        if ref_id and not task_context.get("task_id"):
            task_context["task_id"] = str(ref_id)
        return {
            "intent": target_intent.value,
            "confidence": 1.0,
            "active_agent": "review_agent",
            "task_context": task_context,
            "referenced_task_id": str(ref_id) if ref_id else None,
            "confirmed": True,
            "needs_confirmation": False,
            "pending_confirmation": pending,
            "tool_calls_made": state.get("tool_calls_made", []),
        }

    referenced_id = resolve_references(raw_message, history) or state.get("referenced_task_id")
    classification = await classify_intent(raw_message)

    task_context = classification.task_context.model_dump()
    if referenced_id and not task_context.get("task_id"):
        task_context["task_id"] = referenced_id

    target_intent = classification.intent
    active_agent = ROUTING_MAP.get(target_intent, "task_agent")

    return {
        "intent": target_intent.value,
        "confidence": classification.confidence,
        "active_agent": active_agent,
        "task_context": task_context,
        "referenced_task_id": referenced_id or task_context.get("task_id"),
        "tool_calls_made": state.get("tool_calls_made", []),
    }
