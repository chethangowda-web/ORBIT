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

    # Assignee and title extraction for "create" commands
    action_match = re.search(r"\bfor\s+(.+?)\s+to\s+(.+?)(?:\s+by\s+[A-Za-z0-9\-]+)?$", user_message, re.IGNORECASE)
    if action_match:
        ctx.assignee_name = action_match.group(1).strip()
        ctx.title = action_match.group(2).strip().capitalize()
    else:
        assignee_match = re.search(r"\b(?:for|to)\s+([A-Z][a-z]+|[a-z]+)\b", user_message)
        if assignee_match:
            ctx.assignee_name = assignee_match.group(1).capitalize()

    # Intent routing
    if any(w in msg for w in ["what should i focus on", "plan my day", "daily plan", "plan for today", "priorities today"]):
        return IntentClassificationResult(intent=Intent.PLAN_DAY, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["overdue", "delayed tasks"]):
        return IntentClassificationResult(intent=Intent.GET_OVERDUE_TASKS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["recommendation", "insight", "workload", "bottleneck"]):
        return IntentClassificationResult(intent=Intent.GET_RECOMMENDATIONS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["help", "what can you do", "commands"]):
        return IntentClassificationResult(intent=Intent.HELP, confidence=1.0, task_context=ctx)
    if any(w in msg for w in ["delete", "remove task", "trash"]):
        ctx.title_hint = user_message.replace("delete", "").replace("the", "").replace("task", "").strip()
        return IntentClassificationResult(intent=Intent.DELETE_TASK, confidence=0.90, task_context=ctx)
    if any(w in msg for w in ["mark as done", "mark as completed", "complete the task", "finish task", "completed", "mark "]):
        ctx.title_hint = re.sub(r"(?i)\b(mark|as|completed|done|the|task|finish)\b", "", user_message).strip()
        return IntentClassificationResult(intent=Intent.COMPLETE_TASK, confidence=0.90, task_context=ctx)
    if any(w in msg for w in ["show my tasks", "my pending tasks", "list my tasks", "get my tasks", "my tasks"]):
        return IntentClassificationResult(intent=Intent.GET_MY_TASKS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["search for", "find task", "look for", "search"]):
        ctx.title_hint = re.sub(r"(?i)\b(search for|find task|search|find)\b", "", user_message).strip()
        return IntentClassificationResult(intent=Intent.SEARCH_TASKS, confidence=0.90, task_context=ctx)
    if any(w in msg for w in ["update", "change deadline", "set priority", "reschedule", "modify"]):
        return IntentClassificationResult(intent=Intent.UPDATE_TASK, confidence=0.90, task_context=ctx)
    if any(w in msg for w in ["create", "assign", "add task", "new task", "schedule task"]):
        if not ctx.title:
            clean_title = re.sub(r"(?i)\b(create a (high|low|medium|critical) priority task|create a task|create task|assign)\b", "", user_message)
            clean_title = re.sub(r"(?i)\b(for|to)\s+[A-Za-z]+", "", clean_title)
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
