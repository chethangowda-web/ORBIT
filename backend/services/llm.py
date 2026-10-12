"""LLM service layer utilizing LiteLLM with structured outputs and fallback capabilities."""

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Type, TypeVar
import litellm
from pydantic import BaseModel

from config import settings
from db.base import local_now
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
    now = local_now()
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


MY_TASK_PHRASES = [
    "show my tasks", "my pending tasks", "list my tasks", "get my tasks", "my tasks", "show tasks", "view tasks",
    "on my plate", "what do i have", "what do i need to do", "what is on my list", "what's on my list",
    "my to-do", "my todo", "pending tasks", "open tasks", "list tasks", "assigned to me", "everything assigned",
]

# Messages that start like this ask for information; they must never create, change,
# complete or delete anything, even if they contain words like "created" or "done".
READ_REQUEST_START = (
    r"^\s*(list|show|display|view|give me|tell me|what|which|who|when|where|why|how|is|are|was|were|did|does)\b"
)
TASK_DETAIL_PHRASE = (
    r"\b(status of|who created|who is assigned|who's assigned|details|tell me about|info on|information about|history of)\b"
)


_PLAN_WEEK_RE = re.compile(
    r"\b(?:plan|schedule|organi[sz]e|map\s+out|sort\s+out|prioriti[sz]e)\b.{0,25}\bweek\b"
    r"|\bweekly\s+plan\b|\bweek\s+ahead\b"
    r"|\b(?:what(?:'s|\s+does|\s+is)?|how)\b.{0,15}\bmy\s+week\b.{0,10}\b(?:look|like|ahead)\b"
    r"|\bnext\s+(?:five|5)\s+days\b",
    re.IGNORECASE,
)
# Only a bare "undo" counts, so "undo the deadline on the report task" is never read as an undo.
_UNDO_RE = re.compile(
    r"^\s*(?:please\s+|can\s+you\s+|could\s+you\s+)?(?:undo|revert|roll\s*back|take\s+(?:that|it)\s+back)"
    r"(?:\s+(?:that|it|this|the\s+last(?:\s+(?:change|action|one))?|my\s+last(?:\s+(?:change|action))?|last\s+(?:change|action)|everything))?"
    r"(?:\s+please)?\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_SUGGEST_ASSIGNEE_RE = re.compile(
    r"\bwho\s+(?:should|could|can|would|might)\s+(?:take|do|handle|own|pick\s+up|work\s+on|get|be\s+assigned)\b"
    r"|\bwho(?:'s|\s+is|\s+has|\s+have|\s+got)\s+(?:the\s+)?(?:free|available|capacity|bandwidth|time|room|least|lowest|less\s+busy|not\s+busy|most\s+free)\b"
    r"|\b(?:least|less)\s+busy\b|\bmost\s+available\b"
    r"|\bsuggest\s+(?:an?\s+)?(?:assignee|owner|someone|who)\b"
    r"|\bwho\s+should\s+i\s+(?:assign|give)\b",
    re.IGNORECASE,
)


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
    if _UNDO_RE.search(msg):
        return IntentClassificationResult(intent=Intent.UNDO_LAST, confidence=0.97, task_context=ctx)
    if _PLAN_WEEK_RE.search(msg):
        return IntentClassificationResult(intent=Intent.PLAN_WEEK, confidence=0.95, task_context=ctx)
    if _SUGGEST_ASSIGNEE_RE.search(msg):
        return IntentClassificationResult(intent=Intent.SUGGEST_ASSIGNEE, confidence=0.95, task_context=ctx)
    plan_phrases = [
        "what should i focus on", "plan my day", "daily plan", "plan for today", "priorities today", "focus today",
        "prioritize", "prioritise", "work on first", "work on next", "what should i work on", "what should i do",
        "what to do first", "my plan for the day", "plan for the day", "tackle", "order my work", "by importance",
    ]
    if any(w in msg for w in plan_phrases):
        return IntentClassificationResult(intent=Intent.PLAN_DAY, confidence=0.95, task_context=ctx)
    overdue_pattern = r"\b(overdue|late|past (?:its |their |the )?(?:due|deadline)|behind schedule|behind on|slipped|missed (?:the |its )?deadline|delayed tasks)\b"
    if re.search(overdue_pattern, msg):
        return IntentClassificationResult(intent=Intent.GET_OVERDUE_TASKS, confidence=0.95, task_context=ctx)
    if any(w in msg for w in ["recommendation", "recommendations", "insight", "insights", "workload", "bottleneck", "bottlenecks", "overloaded", "how is the team", "how's the team", "team doing"]):
        return IntentClassificationResult(intent=Intent.GET_RECOMMENDATIONS, confidence=0.95, task_context=ctx)
    is_help = (
        msg.strip("?! .") in {"help", "commands", "menu"}
        or (msg.startswith("help") and len(msg.split()) <= 2)
        or any(w in msg for w in ["what can you do", "what you can do", "what do you do", "how do i use", "how does this work", "list commands", "commands are available", "what commands"])
    )
    if is_help:
        return IntentClassificationResult(intent=Intent.HELP, confidence=1.0, task_context=ctx)

    greeting = re.match(
        r"^\s*(?:(?:hi+|hel+o+|hey+|yo|hiya|howdy|namaste|good\s+(?:morning|afternoon|evening)|thanks?(?:\s+you)?|thx|cheers)\b[\s,!.]*)+(?:orbit|there|team|bot|everyone)?[\s!.]*$",
        msg,
    )
    if greeting and len(msg.split()) <= 5:
        return IntentClassificationResult(intent=Intent.GREETING, confidence=0.95, task_context=ctx)

    if re.match(READ_REQUEST_START, msg):
        if re.search(TASK_DETAIL_PHRASE, msg):
            hint = re.sub(
                r"(?i)^.*?\b(?:status of|who created|details (?:of|for|on)|tell me about|info on|information about|history of)\s+(?:the\s+)?",
                "",
                user_message,
            ).strip(" ?.")
            ctx.title_hint = hint or None
            return IntentClassificationResult(intent=Intent.GET_TASK_DETAIL, confidence=0.9, task_context=ctx)
        if any(w in msg for w in MY_TASK_PHRASES) or re.search(r"\b(tasks?|work|assigned|done|finish\w*|completed|created)\b", msg):
            return IntentClassificationResult(intent=Intent.GET_MY_TASKS, confidence=0.85, task_context=ctx)
        if not re.search(r"\b(search|find|look up|mentioning)\b", msg):
            return IntentClassificationResult(intent=Intent.UNKNOWN, confidence=0.5, task_context=ctx)

    remind = re.match(r"^\s*(?:please\s+)?(?:remind me to|(?:put|set|add) (?:a )?reminder to)\s+(.+)$", user_message, re.IGNORECASE)
    if remind:
        title = re.sub(
            r"(?i)\s+(?:by|on|before|for)?\s*(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.*$",
            "",
            remind.group(1),
        ).strip()
        ctx.title = title.capitalize() if title else "New task"
        return IntentClassificationResult(intent=Intent.CREATE_TASK, confidence=0.9, task_context=ctx)

    # CREATE_TASK (checked before completion/search to prevent "create a task to finish..." collision)
    polite_create = re.match(r"^\s*(?:could you |can you |please |i need |i want )*(?:to )?(?:add|create|make|schedule)?\s*(?:a |an )?(?:new )?task\b", msg) and re.search(r"\b(add|create|make|schedule|need|want)\b", msg)
    if any(msg.startswith(p) for p in ["create", "add task", "add a task", "new task", "schedule a task", "schedule task"]) or "create a task" in msg or "create task" in msg or "add a task" in msg or polite_create:
        if not ctx.title:
            clean_title = re.sub(
                r"(?i)^\s*(create\s+a\s+(high|low|medium|critical)\s+priority\s+task\s+(to|for)|create\s+a\s+task\s+(to|for)|create\s+a\s+task|create\s+task\s+(to|for)|create\s+task|add\s+a\s+task\s+(to|for)|add\s+a\s+task|add\s+task\s+(to|for)|add\s+task|new\s+task|(?:could|can)\s+you\s+(?:please\s+)?add\s+a\s+task(?:\s+(?:to|for))?|i\s+need\s+a\s+task(?:\s+(?:to|for))?)\b",
                "",
                user_message,
            ).strip()
            clean_title = re.sub(r"(?i),?\s*(low|medium|high|critical|urgent)\s+priority\b", "", clean_title).strip()
            if ctx.assignee_name:
                clean_title = re.sub(rf"(?i)\b(?:for|to)\s+{re.escape(ctx.assignee_name)}\b", "", clean_title).strip()
            clean_title = re.sub(r"(?i)\bby\s+[A-Za-z0-9\-]+", "", clean_title).strip()
            ctx.title = clean_title.capitalize() if clean_title else "New Task"
        return IntentClassificationResult(intent=Intent.CREATE_TASK, confidence=0.95, task_context=ctx)

    if any(w in msg for w in ["delete", "remove task", "trash"]) or re.match(r"^\s*(remove|drop|get rid of)\b", msg):
        clean = re.sub(r"(?i)^\s*(delete|remove|drop|trash|get rid of)\s+(the\s+)?(task\s+)?", "", user_message)
        clean = re.sub(r"(?i)\s+task$", "", clean).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.DELETE_TASK, confidence=0.90, task_context=ctx)

    done_phrase = re.match(
        r"(?i)^\s*(?:the\s+)?(.+?)\s+(?:task\s+)?(?:is|are|has been|have been)\s+(?:now\s+)?(?:done|complete[d]?|finished)\s*[.!]?\s*$",
        user_message,
    )
    set_done = re.match(r"(?i)^\s*set\s+(?:the\s+)?(.+?)\s+(?:task\s+)?to\s+(?:done|complete[d]?)\s*[.!]?\s*$", user_message)
    done_with = re.match(r"(?i)^\s*(?:i'?m|i am|we'?re|we are)\s+done\s+with\s+(?:the\s+)?(.+?)\s*[.!]?\s*$", user_message)
    for matched in (set_done, done_with):
        if matched:
            ctx.title_hint = matched.group(1).strip()
            return IntentClassificationResult(intent=Intent.COMPLETE_TASK, confidence=0.9, task_context=ctx)
    if done_phrase and "?" not in user_message:
        ctx.title_hint = done_phrase.group(1).strip()
        return IntentClassificationResult(intent=Intent.COMPLETE_TASK, confidence=0.9, task_context=ctx)

    if any(w in msg for w in ["mark as done", "mark as completed", "complete the task", "finish task", "completed", "complete", "finish", "mark"]):
        clean = re.sub(r"(?i)^\s*(?:i\s+)?(?:just\s+)?(mark|complete[d]?|finish(?:ed)?|wrapped up|done with)\s+(the\s+)?", "", user_message)
        clean = re.sub(r"(?i)\s+task\s*(as\s+completed|as\s+done)?$", "", clean)
        clean = re.sub(r"(?i)\s+(as\s+completed|as\s+done|completed|done)$", "", clean).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.COMPLETE_TASK, confidence=0.90, task_context=ctx)

    if re.search(r"\b(what|which)\b.*\btasks?\b.*\b(do i have|i have|are open|is open)\b", msg):
        return IntentClassificationResult(intent=Intent.GET_MY_TASKS, confidence=0.9, task_context=ctx)
    if any(w in msg for w in MY_TASK_PHRASES):
        return IntentClassificationResult(intent=Intent.GET_MY_TASKS, confidence=0.95, task_context=ctx)

    if any(w in msg for w in ["details", "history of task", "task info", "show details"]):
        return IntentClassificationResult(intent=Intent.GET_TASK_DETAIL, confidence=0.90, task_context=ctx)

    if any(w in msg for w in ["search for", "find task", "look for", "look up", "search", "mentioning"]) or re.match(r"^\s*find\b", msg):
        clean = re.sub(r"(?i)^\s*(search for|find tasks?|search|find|look up|look for)\s+(?:tasks?\s+)?(?:about\s+|mentioning\s+)?(the\s+)?", "", user_message).strip()
        ctx.title_hint = clean if clean else user_message
        return IntentClassificationResult(intent=Intent.SEARCH_TASKS, confidence=0.90, task_context=ctx)
    
    # Follow-up modifications (e.g. "make it high priority", "change its priority to critical", "move that deadline to Friday")
    followup_update_triggers = [
        "push the deadline", "push back the deadline", "bump this to", "bump it to", "reassign",
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


    if re.match(r"^\s*assign\b", msg) or any(w in msg for w in ["create", "add task", "new task", "schedule task"]):
        if not ctx.title:
            clean_title = re.sub(r"(?i)\b(create a (high|low|medium|critical) priority task|create a task|create task|assign)\b", "", user_message)
            clean_title = re.sub(r"(?i)\b(for|to)\s+[A-Za-z0-9_]+", "", clean_title)
            clean_title = re.sub(r"(?i)\bby\s+[A-Za-z0-9\-]+", "", clean_title).strip()
            ctx.title = clean_title.capitalize() if clean_title else "New Task"
        return IntentClassificationResult(intent=Intent.CREATE_TASK, confidence=0.95, task_context=ctx)

    return IntentClassificationResult(intent=Intent.UNKNOWN, confidence=0.5, task_context=ctx)


class LLMCircuitBreaker:
    """Stops calling a failing provider for a cooldown, so an outage or exhausted quota costs
    nothing per message: callers fall straight through to the offline rule-based path."""

    def __init__(self) -> None:
        self.failures = 0
        self.opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= settings.LLM_BREAKER_COOLDOWN_SECONDS:
            self.opened_at = None  # half-open: let one request probe the provider
            self.failures = settings.LLM_BREAKER_FAILURES - 1
            return True
        return False

    def is_available(self) -> bool:
        """True when a call would be attempted (closed, or the cooldown is over). Changes no state."""
        return self.opened_at is None or time.monotonic() - self.opened_at >= settings.LLM_BREAKER_COOLDOWN_SECONDS

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= settings.LLM_BREAKER_FAILURES and self.opened_at is None:
            self.opened_at = time.monotonic()
            logger.warning("LLM circuit opened for %.0fs after %d failures", settings.LLM_BREAKER_COOLDOWN_SECONDS, self.failures)


llm_breaker = LLMCircuitBreaker()


class ModelPool:
    """The models to try, in order, and which of them are resting after hitting a quota."""

    def __init__(self) -> None:
        self.blocked_until: dict[str, float] = {}

    def models(self) -> list[str]:
        chain = [getattr(settings, "DEFAULT_LLM_MODEL", "")] + [m.strip() for m in settings.LLM_FALLBACK_MODELS.split(",")]
        seen: list[str] = []
        for model in chain:
            if model and model not in seen:
                seen.append(model)
        return seen

    def candidates(self) -> list[str]:
        now = time.monotonic()
        return [m for m in self.models() if self.blocked_until.get(m, 0.0) <= now]

    def block(self, model: str, seconds: float) -> None:
        self.blocked_until[model] = time.monotonic() + max(1.0, min(seconds, settings.LLM_MAX_BLOCK_SECONDS))
        logger.warning("Model %s is resting for %.0fs (quota or availability)", model, min(seconds, settings.LLM_MAX_BLOCK_SECONDS))


model_pool = ModelPool()

_RETRY_DELAY = re.compile(r'retryDelay"?\s*[:=]\s*"?(\d+(?:\.\d+)?)s', re.IGNORECASE)


def _is_rate_limited(err: Exception) -> bool:
    text = str(err)
    return isinstance(err, litellm.RateLimitError) or "429" in text or "RESOURCE_EXHAUSTED" in text


def _is_missing_model(err: Exception) -> bool:
    return isinstance(err, litellm.NotFoundError) or "NOT_FOUND" in str(err)


def _is_busy(err: Exception) -> bool:
    """The provider is overloaded right now (HTTP 503). Not the model's fault: do not rest it."""
    text = str(err)
    return isinstance(err, litellm.ServiceUnavailableError) or "503" in text or "UNAVAILABLE" in text or "high demand" in text


def _retry_after(err: Exception) -> float:
    found = _RETRY_DELAY.search(str(err))
    return float(found.group(1)) if found else 60.0


async def _complete(timeout: float, **kwargs: Any) -> Any:
    """litellm.acompletion across the model chain. A model that is out of quota or gone is skipped (and
    rests for a while) and the next one is tried at once; any other error is the caller's to handle."""
    last: Optional[Exception] = None
    for model in model_pool.candidates():
        try:
            return await asyncio.wait_for(litellm.acompletion(model=model, timeout=timeout, **kwargs), timeout=timeout + 2)
        except Exception as err:
            if _is_rate_limited(err):
                model_pool.block(model, _retry_after(err))
            elif _is_missing_model(err):
                model_pool.block(model, settings.LLM_MAX_BLOCK_SECONDS)
            elif not _is_busy(err):
                raise
            last = err
    raise last or RuntimeError("No AI model is available right now.")


def llm_available() -> bool:
    """Is there an API key, and is the provider not currently paused by the circuit breaker?"""
    key = getattr(settings, "GOOGLE_GEMINI_API_KEY", "") or getattr(settings, "OPENAI_API_KEY", "")
    return bool(key) and llm_breaker.is_available() and bool(model_pool.candidates())


async def call_llm_with_tools(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_tokens: int = 1200,
    timeout: Optional[float] = None,
) -> Optional[Any]:
    """One model turn with function calling. Returns the assistant message (``content`` and
    ``tool_calls``), or None when the model cannot answer in time. Same key check, timeout and circuit
    breaker as call_llm: a failing provider never blocks the caller."""
    api_key = getattr(settings, "GOOGLE_GEMINI_API_KEY", "") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key or not model_pool.candidates() or not llm_breaker.allow():
        return None
    limit = timeout or settings.LLM_TIMEOUT_SECONDS
    try:
        try:
            response = await _complete(
                limit, messages=messages, tools=tools, tool_choice="auto", temperature=0.1, max_tokens=max_tokens, api_key=api_key
            )
        except Exception as first:
            if not _is_busy(first) or not model_pool.candidates():
                raise
            await asyncio.sleep(1.5)  # demand spikes are short; one more pass through the models
            response = await _complete(
                limit, messages=messages, tools=tools, tool_choice="auto", temperature=0.1, max_tokens=max_tokens, api_key=api_key
            )
        llm_breaker.record_success()
        return response.choices[0].message
    except Exception as err:
        logger.warning("LLM tool call failed: %s", err)
        llm_breaker.record_failure()
        return None


async def call_llm(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1000,
    response_model: Optional[Type[T]] = None,
    retries: Optional[int] = None,
) -> Optional[Any]:
    """Execute LLM call via LiteLLM with structured output, a per-attempt timeout, bounded retries
    and a circuit breaker. Returns None whenever the provider cannot answer in time."""
    api_key = getattr(settings, "GOOGLE_GEMINI_API_KEY", "") or getattr(settings, "OPENAI_API_KEY", "")
    if not api_key or not model_pool.candidates():
        return None
    if not llm_breaker.allow():
        return None

    retries = retries or settings.LLM_MAX_ATTEMPTS
    for attempt in range(retries):
        try:
            kwargs: dict[str, Any] = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "api_key": api_key,
            }
            if response_model:
                kwargs["response_format"] = response_model

            response = await _complete(settings.LLM_TIMEOUT_SECONDS, **kwargs)
            content = response.choices[0].message.content
            llm_breaker.record_success()
            if response_model and isinstance(content, str):
                try:
                    return response_model.model_validate_json(content)
                except Exception:
                    pass
            return content
        except Exception as err:
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, err)
            llm_breaker.record_failure()
            if attempt == retries - 1 or not llm_breaker.allow():
                return None
            await asyncio.sleep(1)
    return None
