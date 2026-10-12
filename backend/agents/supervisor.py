"""Supervisor Agent: Intent classification and specialist agent routing."""

from typing import Any
from agents.intents import (
    Intent,
    IntentClassificationResult,
)
from agents.memory_agent import mentions_previous_task, resolve_references
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


_FILLER_WORDS = {
    "a", "an", "the", "as", "it", "its", "this", "that", "these", "those", "one", "task", "tasks", "done",
    "complete", "completed", "finished", "finish", "my", "me", "now", "please", "is", "was", "to", "of",
    "and", "or", "on", "for", "with", "mark", "set",
}


def _meaningful_hint(hint: Any) -> bool:
    """A task title hint that carries at least one real word. Extractors sometimes return filler
    such as "as" (from "mark as done"); that must not count as naming a task."""
    words = [w for w in str(hint or "").lower().replace("'", " ").split() if w.strip(".,!?")]
    return any(w.strip(".,!?") not in _FILLER_WORDS and len(w.strip(".,!?")) >= 3 for w in words)


# Intents that may continue with "the task we were just talking about" when no task is named.
FOLLOW_UP_INTENTS = {Intent.UPDATE_TASK, Intent.COMPLETE_TASK, Intent.GET_TASK_DETAIL}


async def classify_intent_with_source(raw_message: str) -> tuple[IntentClassificationResult, str]:
    """Classifies user intent with the LLM, or with the deterministic rules when the LLM is not
    configured, slow or failing. Returns (result, "llm" | "rules")."""
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
        return res, "llm"
    return fallback_intent_classifier(raw_message), "rules"


async def classify_intent(raw_message: str) -> IntentClassificationResult:
    """Classifies user intent (see classify_intent_with_source)."""
    return (await classify_intent_with_source(raw_message))[0]


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
            "classifier": "flow",
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
            "classifier": "flow",
            "active_agent": "review_agent",
            "task_context": task_context,
            "referenced_task_id": str(ref_id) if ref_id else None,
            "confirmed": True,
            "needs_confirmation": False,
            "pending_confirmation": pending,
            "tool_calls_made": state.get("tool_calls_made", []),
        }

    classification, classifier = await classify_intent_with_source(raw_message)
    task_context = classification.task_context.model_dump()

    # The previous task is only the target when the user refers back to it ("make it high
    # priority"). Reusing it for every message made "complete the report task" act on whatever
    # task was mentioned last, instead of searching or asking which one was meant.
    referenced_id = None
    target_intent = classification.intent
    names_a_task = bool(task_context.get("task_id") or _meaningful_hint(task_context.get("title_hint")))
    # A message that names a task never inherits the previous one. One that names none ("mark as
    # done", "move that deadline to Friday") means the task just discussed, for edits that cannot
    # do much harm. Deleting needs an explicit reference ("delete it") on top of its confirmation.
    inherits_previous = not names_a_task and (
        mentions_previous_task(raw_message) or target_intent in FOLLOW_UP_INTENTS
    )
    if inherits_previous:
        referenced_id = resolve_references(raw_message, history) or state.get("referenced_task_id")
        if referenced_id:
            task_context["task_id"] = str(referenced_id)

    active_agent = ROUTING_MAP.get(target_intent, "task_agent")

    return {
        "intent": target_intent.value,
        "confidence": classification.confidence,
        "classifier": classifier,
        "active_agent": active_agent,
        "task_context": task_context,
        "referenced_task_id": referenced_id or task_context.get("task_id"),
        "tool_calls_made": state.get("tool_calls_made", []),
        # A new request ends any earlier question: a later "yes" must never answer a delete
        # prompt from a different part of the conversation, and a cancelled action's reply must
        # not be repeated on every following turn. These values persist in the checkpoint.
        "needs_confirmation": False,
        "confirmed": False,
        "pending_confirmation": None,
        "response": "",
    }
