"""LLM service layer utilizing LiteLLM with structured outputs and fallback capabilities."""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Type, TypeVar
import litellm
from pydantic import BaseModel

from config import settings
from agents.intents import (
    Intent,
    IntentClassificationResult,
    TaskContextExtraction,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def resolve_relative_date(relative_str: Optional[str]) -> Optional[str]:
    """Resolves relative date strings like 'Friday', 'tomorrow', 'next Monday' to ISO dates."""
    if not relative_str:
        return None
    now = datetime.now(timezone.utc)
    rel = relative_str.strip().lower()

    if "today" in rel:
        return now.strftime("%Y-%m-%d")
    if "tomorrow" in rel:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")

    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
    }
    for day_name, day_idx in weekdays.items():
        if day_name in rel:
            days_ahead = (day_idx - now.weekday()) % 7
            if days_ahead <= 0:
                days_ahead += 7
            if "next" in rel:
                days_ahead += 7
            return (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    iso_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", relative_str)
    if iso_match:
        return iso_match.group(0)
    return None


def fallback_intent_classifier(user_message: str) -> IntentClassificationResult:
    """Deterministic rule-based intent and context extractor for offline/test reliability."""
    msg = user_message.strip().lower()
    ctx = TaskContextExtraction()

    # UUID extraction
    uuid_match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        user_message,
    )
    if uuid_match:
        ctx.task_id = uuid_match.group(0)

    # Priority extraction
    if "critical" in msg:
        ctx.priority = "CRITICAL"
    elif "high" in msg or "urgent" in msg:
        ctx.priority = "HIGH"
    elif "low" in msg:
        ctx.priority = "LOW"
    elif "medium" in msg:
        ctx.priority = "MEDIUM"

    # Date extraction
    for date_word in ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        if date_word in msg:
            ctx.due_date_relative = date_word.capitalize()
            ctx.due_date = resolve_relative_date(date_word)
            break

    date_words = {"today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    non_assignee_words = {
        "today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "finish", "complete", "deploy", "build", "review", "implement", "update", "test", "fix", "prepare", "write",
        "send", "check", "create", "delete", "schedule", "buy", "call", "do", "make", "find", "search", "show", "get", "list",
        "the", "a", "an", "it", "that", "this", "my", "our", "all", "high", "medium", "low", "critical"
    }

    # Assignee and title extraction for "create" or "update" commands
    action_match = re.search(r"\bfor\s+(.+?)\s+to\s+(.+?)(?:\s+by\s+[A-Za-z0-9\-]+)?$", user_message, re.IGNORECASE)
    if action_match:
        cand_name = action_match.group(1).strip()
        if cand_name.lower() not in non_assignee_words:
            ctx.assignee_name = cand_name
        ctx.title = action_match.group(2).strip().capitalize()
    else:
        assign_to_match = re.search(r"\b(?:to|for)\s+([A-Za-z0-9_]+)\b", user_message, re.IGNORECASE)
        if assign_to_match:
            cand = assign_to_match.group(1)
            if cand.lower() not in non_assignee_words:
                ctx.assignee_name = cand

    # Intent routing
    if any(w in msg for w in ["what should i focus on", "plan my day", "daily plan", "plan for today", "priorities today", "focus today"]):
        return IntentClassificationResult(intent=Intent.PLAN_DAY, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["overdue", "delayed tasks"]):
        return IntentClassificationResult(intent=Intent.GET_OVERDUE_TASKS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["recommendation", "recommendations", "insight", "insights", "workload", "bottleneck", "bottlenecks"]):
        return IntentClassificationResult(intent=Intent.GET_RECOMMENDATIONS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["help", "what can you do", "commands"]):
        return IntentClassificationResult(intent=Intent.HELP, confidence=1.0, task_context=ctx)

    # CREATE_TASK (checked before completion/search to prevent "create a task to finish..." collision)
    if any(msg.startswith(p) for p in ["create", "add task", "add a task", "new task", "schedule a task", "schedule task"]) or "create a task" in msg or "create task" in msg:
        if not ctx.title:
            clean_title = re.sub(
                r"(?i)^\s*(create\s+a\s+(high|low|medium|critical)\s+priority\s+task\s+(to|for)|create\s+a\s+task\s+(to|for)|create\s+a\s+task|create\s+task\s+(to|for)|create\s+task|add\s+a\s+task\s+(to|for)|add\s+a\s+task|add\s+task\s+(to|for)|add\s+task|new\s+task)\b",
                "",
                user_message,
            ).strip()
            if ctx.assignee_name:
                clean_title = re.sub(rf"(?i)\b(?:for|to)\s+{re.escape(ctx.assignee_name)}\b", "", clean_title).strip()
            clean_title = re.sub(r"(?i)\bby\s+[A-Za-z0-9\-]+", "", clean_title).strip()
            ctx.title = clean_title.capitalize() if clean_title else "New Task"
        return IntentClassificationResult(intent=Intent.CREATE_TASK, confidence=0.95, task_context=ctx)

    if any(w in msg for w in ["delete", "remove task", "trash"]):
        clean = re.sub(r"(?i)^\s*(delete|remove|trash)\s+(the\s+)?(task\s+)?", "", user_message)
        clean = re.sub(r"(?i)\s+task$", "", clean).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.DELETE_TASK, confidence=0.90, task_context=ctx)

    if any(w in msg for w in ["mark as done", "mark as completed", "complete the task", "finish task", "completed", "complete", "finish", "mark"]):
        clean = re.sub(r"(?i)^\s*(mark|complete|finish)\s+(the\s+)?", "", user_message)
        clean = re.sub(r"(?i)\s+task\s*(as\s+completed|as\s+done)?$", "", clean)
        clean = re.sub(r"(?i)\s+(as\s+completed|as\s+done|completed|done)$", "", clean).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.COMPLETE_TASK, confidence=0.90, task_context=ctx)

    if any(w in msg for w in ["show my tasks", "my pending tasks", "list my tasks", "get my tasks", "my tasks", "show tasks", "view tasks"]):
        return IntentClassificationResult(intent=Intent.GET_MY_TASKS, confidence=0.95, task_context=ctx)

    if any(w in msg for w in ["details", "history of task", "task info", "show details"]):
        return IntentClassificationResult(intent=Intent.GET_TASK_DETAIL, confidence=0.90, task_context=ctx)

    if any(w in msg for w in ["search for", "find task", "look for", "search"]):
        clean = re.sub(r"(?i)^\s*(search for|find task|search|find)\s+(the\s+)?", "", user_message).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.SEARCH_TASKS, confidence=0.90, task_context=ctx)
    
    # Follow-up modifications (e.g. "make it high priority", "change its priority to critical", "move that deadline to Friday")
    followup_update_triggers = [
        "make it", "set priority", "change priority", "change deadline", "move deadline",
        "move that deadline", "update deadline", "assign that to", "assign it to", "assign task",
        "reschedule", "modify", "update", "rename", "change status", "set status",
        "make its", "change its", "set its", "update its"
    ]
    is_field_update = bool(re.search(r"\b(change|update|set|make|move)\b.*?\b(priority|deadline|due date|status)\b", msg, re.IGNORECASE))
    if any(trig in msg for trig in followup_update_triggers) or (ctx.task_id and "assign" in msg) or is_field_update:
        # Extract title hint if updating specific task by name
        if "update " in msg and ("priority" in msg or "deadline" in msg or "due date" in msg or "status" in msg):
            hint_match = re.search(r"update\s+(?:the\s+)?(.+?)\s+(?:deadline|due date|priority|status)", user_message, re.IGNORECASE)
            if hint_match:
                ctx.title_hint = hint_match.group(1).strip()
        return IntentClassificationResult(intent=Intent.UPDATE_TASK, confidence=0.95, task_context=ctx)


    if any(w in msg for w in ["create", "assign", "add task", "new task", "schedule task"]):
        if not ctx.title:
            clean_title = re.sub(r"(?i)\b(create a (high|low|medium|critical) priority task|create a task|create task|assign)\b", "", user_message)
            clean_title = re.sub(r"(?i)\b(for|to)\s+[A-Za-z0-9_]+", "", clean_title)
            clean_title = re.sub(r"(?i)\bby\s+[A-Za-z0-9\-]+", "", clean_title).strip()
            ctx.title = clean_title.capitalize() if clean_title else "New Task"
        return IntentClassificationResult(intent=Intent.CREATE_TASK, confidence=0.95, task_context=ctx)

    return IntentClassificationResult(intent=Intent.UNKNOWN, confidence=0.5, task_context=ctx)


async def call_llm(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1000,
    response_model: Optional[Type[T]] = None,
    retries: int = 3,
) -> Optional[Any]:
    """Execute LLM call via LiteLLM with structured output support and exponential backoff."""
    api_key = getattr(settings, "GOOGLE_GEMINI_API_KEY", "") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None

    for attempt in range(retries):
        try:
            kwargs: dict[str, Any] = {
                "model": getattr(settings, "DEFAULT_LLM_MODEL", "gemini/gemini-1.5-pro"),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": api_key,
            }
            if response_model:
                kwargs["response_format"] = response_model

            response = await litellm.acompletion(**kwargs)
            content = response.choices[0].message.content
            if response_model and isinstance(content, str):
                try:
                    return response_model.model_validate_json(content)
                except Exception:
                    pass
            return content
        except Exception as err:
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, err)
            if attempt == retries - 1:
                return None
            await asyncio.sleep(2 ** attempt)
    return None
