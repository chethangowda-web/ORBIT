"""Tool-using agent: the model plans and chains tool calls for requests that need several steps.

The other specialists run a fixed handler per request type. This one lets the LLM decide which tools
to call, in what order, and when it is done ("move all of John's overdue tasks to Rahul and make them
high priority": search, look up the person, then update each task).

The model is trusted to plan, never to authorise. Safety is enforced here and in the tools:
* identity (who is asking) is injected by the agent; the model cannot pass or change it;
* every tool re-checks permissions exactly like the REST API does, so an employee cannot read or
  change what they could not in the dashboard;
* deleting is not offered at all (it keeps its own confirmation flow);
* the run is bounded: a few model turns, a time budget, a cap on changes, no repeated identical change;
* the reply lists what really changed from the tools' own results, so it cannot claim more than was done.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from agents.prompts import TOOL_AGENT_PROMPT
from agents.state import AgentState
from config import settings
from crud import users as user_crud
from db.base import local_today
from services.llm import call_llm_with_tools, llm_available
from services.wording import friendly
from tools.base import get_tool_session, resolve_user_reference
from tools.analytics_tools import get_task_stats
from tools.task_tools import complete_task, create_task, get_task_by_id, search_tasks, update_task
from tools.user_tools import get_all_users, get_team_workload

logger = logging.getLogger(__name__)

MAX_STEPS = 6  # model turns per request
MAX_CHANGES = 10  # tasks one request may create or change
RUN_BUDGET_SECONDS = 12.0  # classification takes a few seconds first; the whole request must fit in AGENT_TIMEOUT_SECONDS
MAX_LISTED_TASKS = 25
MAX_RESULT_CHARS = 6000
MAX_REPLY_CHARS = 1800

BUSY_REPLY = (
    "I can't work through bigger requests right now because the AI is busy. "
    "Try one simple request at a time, like *show my overdue tasks*, or ask again in a minute."
)
EMPTY_REPLY = "I looked into it but have nothing to report. Could you tell me a bit more about what you need?"

_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)


@dataclass
class RunContext:
    """Everything one request needs, with the caller's identity fixed up front."""

    user_id: str
    tools_used: list[str] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)  # one entry per create/update/complete attempt
    titles: dict[str, str] = field(default_factory=dict)  # task id -> title, learned from results
    seen: dict[str, str] = field(default_factory=dict)  # identical call -> its result, so repeats do nothing
    last_task_id: Optional[str] = None

    @property
    def change_count(self) -> int:
        return len(self.changes)


@dataclass
class ToolSpec:
    schema: dict[str, Any]
    handler: Callable[[dict[str, Any], RunContext], Awaitable[Any]]
    allowed: frozenset[str]
    mutating: bool = False


def _fn(name: str, description: str, properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)},
        },
    }


_STATUS = {"type": "string", "enum": ["TODO", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED"]}
_PRIORITY = {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
_DATE = {"type": "string", "description": "Date as YYYY-MM-DD"}


# --- compact results: the model gets only what it needs -----------------------------------------------


def _value(item: Any) -> Any:
    return getattr(item, "value", item)


def _task_view(task: dict[str, Any]) -> dict[str, Any]:
    assignee = task.get("assignee")
    return {
        "id": str(task.get("id")),
        "title": task.get("title"),
        "status": _value(task.get("status")),
        "priority": _value(task.get("priority")),
        "due_date": str(task["due_date"]) if task.get("due_date") else None,
        "assignee": assignee.get("display_name") if isinstance(assignee, dict) else None,
        "days_overdue": task.get("days_overdue") or None,
    }


def _remember_titles(ctx: RunContext, tasks: list[dict[str, Any]]) -> None:
    for task in tasks:
        if task.get("id") and task.get("title"):
            ctx.titles[str(task["id"])] = str(task["title"])


def _task_result(result: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    if not result.get("success"):
        return {"ok": False, "error": result.get("error") or "That did not work."}
    data = result.get("data")
    rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    views = [_task_view(t) for t in rows[:MAX_LISTED_TASKS]]
    _remember_titles(ctx, rows)
    out: dict[str, Any] = {"ok": True, "count": result.get("count", len(views)), "tasks": views}
    if len(rows) > MAX_LISTED_TASKS:
        out["note"] = f"Showing the first {MAX_LISTED_TASKS}; narrow the search to see others."
    return out


# --- handlers ----------------------------------------------------------------------------------------


async def _search(args: dict[str, Any], ctx: RunContext) -> Any:
    payload: dict[str, Any] = {
        "viewer_id": ctx.user_id,
        "include_completed": bool(args.get("include_completed", False)),
        "limit": max(1, min(int(args.get("limit") or 20), MAX_LISTED_TASKS)),
    }
    for key in ("query", "status", "priority", "due_before", "due_after"):
        if args.get(key) is not None:
            payload[key] = args[key]
    if args.get("assignee_name"):
        async with get_tool_session() as db:
            person, problem = await resolve_user_reference(db, str(args["assignee_name"]))
        if problem:
            return {"success": False, "error": problem}
        payload["assignee_id"] = str(person.id)
    return await search_tasks.ainvoke(payload)


async def _get_task(args: dict[str, Any], ctx: RunContext) -> Any:
    return await get_task_by_id.ainvoke({"task_id": args["task_id"], "viewer_id": ctx.user_id})


async def _find_person(args: dict[str, Any], ctx: RunContext) -> Any:
    async with get_tool_session() as db:
        matches = await user_crud.find_users_by_name(db, str(args["name"]))
        people = [{"name": u.display_name, "role": u.role} for u in matches[:8]]
    if not people:
        return {"success": False, "error": f"No team member matches '{args['name']}'."}
    return {"success": True, "data": people, "count": len(people)}


async def _list_team(args: dict[str, Any], ctx: RunContext) -> Any:
    result = await get_all_users.ainvoke({"limit": 100})
    if result.get("success"):
        result = {**result, "data": [{"name": u["display_name"], "role": u["role"]} for u in result["data"]]}
    return result


async def _team_workload(args: dict[str, Any], ctx: RunContext) -> Any:
    result = await get_team_workload.ainvoke({"viewer_id": ctx.user_id})
    if result.get("success"):
        keep = ("display_name", "assigned_tasks", "completed_tasks", "overdue_tasks", "high_priority_tasks")
        result = {**result, "data": [{k: w.get(k) for k in keep} for w in result["data"]]}
    return result


async def _task_stats(args: dict[str, Any], ctx: RunContext) -> Any:
    return await get_task_stats.ainvoke({"viewer_id": ctx.user_id})


async def _create(args: dict[str, Any], ctx: RunContext) -> Any:
    return await create_task.ainvoke({**args, "created_by_id": ctx.user_id})


async def _update(args: dict[str, Any], ctx: RunContext) -> Any:
    return await update_task.ainvoke({**args, "updated_by_id": ctx.user_id})


async def _complete(args: dict[str, Any], ctx: RunContext) -> Any:
    return await complete_task.ainvoke({**args, "completed_by_id": ctx.user_id})


REGISTRY: dict[str, ToolSpec] = {
    "search_tasks": ToolSpec(
        _fn(
            "search_tasks",
            "Find tasks. Filter by words in the title, by assignee name, status, priority and due dates. "
            "Overdue = due_before yesterday and not completed. Shows only tasks the person is allowed to see.",
            {
                "query": {"type": "string", "description": "Words to look for in the title or description"},
                "assignee_name": {"type": "string", "description": "Person the tasks are assigned to"},
                "status": {"type": "array", "items": _STATUS},
                "priority": {"type": "array", "items": _PRIORITY},
                "due_before": _DATE,
                "due_after": _DATE,
                "include_completed": {"type": "boolean", "description": "Also return done and cancelled tasks"},
                "limit": {"type": "integer", "description": "At most this many tasks (up to 25)"},
            },
        ),
        _search,
        frozenset({"query", "assignee_name", "status", "priority", "due_before", "due_after", "include_completed", "limit"}),
    ),
    "get_task": ToolSpec(
        _fn("get_task", "Open one task by its id (taken from a search result).", {"task_id": {"type": "string"}}, ("task_id",)),
        _get_task,
        frozenset({"task_id"}),
    ),
    "find_person": ToolSpec(
        _fn("find_person", "Check who a name refers to before assigning work to them.", {"name": {"type": "string"}}, ("name",)),
        _find_person,
        frozenset({"name"}),
    ),
    "list_team": ToolSpec(_fn("list_team", "List the people on the team.", {}), _list_team, frozenset()),
    "team_workload": ToolSpec(
        _fn("team_workload", "How many open, finished and overdue tasks each person has. Managers and admins only.", {}),
        _team_workload,
        frozenset(),
    ),
    "task_stats": ToolSpec(
        _fn("task_stats", "Totals: tasks by status and priority, completion rate, overdue count.", {}), _task_stats, frozenset()
    ),
    "create_task": ToolSpec(
        _fn(
            "create_task",
            "Create one task. Leave assignee_name empty to keep it for the person asking.",
            {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": _PRIORITY,
                "assignee_name": {"type": "string"},
                "due_date": _DATE,
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            ("title",),
        ),
        _create,
        frozenset({"title", "description", "priority", "assignee_name", "due_date", "tags"}),
        mutating=True,
    ),
    "update_task": ToolSpec(
        _fn(
            "update_task",
            "Change one task: priority, status, due date, assignee, title, description or tags.",
            {
                "task_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": _PRIORITY,
                "status": _STATUS,
                "assignee_name": {"type": "string"},
                "due_date": _DATE,
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            ("task_id",),
        ),
        _update,
        frozenset({"task_id", "title", "description", "priority", "status", "assignee_name", "due_date", "tags"}),
        mutating=True,
    ),
    "complete_task": ToolSpec(
        _fn(
            "complete_task",
            "Mark one task as done.",
            {"task_id": {"type": "string"}, "completion_note": {"type": "string"}},
            ("task_id",),
        ),
        _complete,
        frozenset({"task_id", "completion_note"}),
        mutating=True,
    ),
}

TOOL_SCHEMAS = [spec.schema for spec in REGISTRY.values()]


# --- describing what happened, in plain words ---------------------------------------------------------


def friendly_error(message: Optional[str]) -> str:
    text = (message or "").strip()
    lower = text.lower()
    if lower.startswith("permission denied"):
        return text.split(":", 1)[-1].strip() or "You don't have permission for that."
    if "could not find" in lower or "more than one person" in lower or "no team member" in lower:
        return text
    if "not found" in lower:
        return "I couldn't find that task."
    return "that didn't work"


def _describe_change(name: str, args: dict[str, Any], title: str) -> str:
    if name == "create_task":
        who = f" for {args['assignee_name']}" if args.get("assignee_name") else ""
        return f"Added *{title}*{who}"
    if name == "complete_task":
        return f"Marked *{title}* as done"
    parts = []
    if args.get("priority"):
        parts.append(f"priority is now {friendly(args['priority']).lower()}")
    if args.get("status"):
        parts.append(f"now {friendly(args['status']).lower()}")
    if args.get("due_date"):
        parts.append(f"due {args['due_date']}")
    if args.get("assignee_name"):
        parts.append(f"now with {args['assignee_name']}")
    if args.get("title"):
        parts.append(f"renamed to *{args['title']}*")
    if args.get("description") or args.get("tags"):
        parts.append("details updated")
    return f"Changed *{title}*" + (f": {', '.join(parts)}" if parts else "")


async def _learn_title(args: dict[str, Any], ctx: RunContext) -> None:
    """Know the task's name before reporting on it, even if the model changed it without searching."""
    task_id = str(args.get("task_id") or "")
    if not task_id or task_id in ctx.titles:
        return
    try:
        found = await get_task_by_id.ainvoke({"task_id": task_id, "viewer_id": ctx.user_id})
    except Exception:
        return
    data = found.get("data") if found.get("success") else None
    if isinstance(data, dict) and data.get("title"):
        ctx.titles[task_id] = str(data["title"])


def _record_change(name: str, args: dict[str, Any], result: dict[str, Any], ctx: RunContext) -> None:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    task_id = str(args.get("task_id") or data.get("id") or "")
    title = str(data.get("title") or ctx.titles.get(task_id) or args.get("title") or "that task")
    if result.get("success"):
        ctx.changes.append({"ok": True, "text": _describe_change(name, args, title)})
        if task_id:
            ctx.titles[task_id] = title
            ctx.last_task_id = task_id
    else:
        ctx.changes.append({"ok": False, "text": f"Couldn't change *{title}*: {friendly_error(result.get('error'))}"})


def clean_reply(text: Optional[str]) -> str:
    """Model text made safe for people: no ids, Chat-style bold, bounded length."""
    cleaned = _UUID.sub("", text or "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"*\1*", cleaned)
    cleaned = re.sub(r"(?m)^[ \t]*[*-][ \t]+(?=\S)", "• ", cleaned)  # "* item" bullets read as "•" in Chat
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:MAX_REPLY_CHARS]


# --- running one tool call --------------------------------------------------------------------------------


async def run_tool_call(name: str, raw_arguments: Any, ctx: RunContext) -> str:
    """Execute one model-requested call and return the JSON the model reads next."""
    spec = REGISTRY.get(name)
    if spec is None:
        return json.dumps({"ok": False, "error": f"There is no tool called {name}."})
    try:
        parsed = json.loads(raw_arguments) if isinstance(raw_arguments, str) and raw_arguments.strip() else (raw_arguments or {})
        if not isinstance(parsed, dict):
            raise ValueError("arguments must be an object")
    except (ValueError, TypeError):
        return json.dumps({"ok": False, "error": "The arguments were not valid. Send a JSON object."})

    # Only the parameters the tool declares; identity fields can never get through.
    args = {k: v for k, v in parsed.items() if k in spec.allowed and v is not None}

    key = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
    if spec.mutating and key in ctx.seen:
        return ctx.seen[key]  # the same change twice does nothing the second time
    if spec.mutating and ctx.change_count >= MAX_CHANGES:
        return json.dumps({"ok": False, "error": f"Change limit reached ({MAX_CHANGES} per request). Stop and tell the person what is left."})

    ctx.tools_used.append(name)
    try:
        result = await spec.handler(args, ctx)
    except Exception as err:  # a tool must never take the whole request down
        logger.warning("Tool %s failed: %s", name, err)
        result = {"success": False, "error": "That did not work."}

    if spec.mutating:
        await _learn_title(args, ctx)
        _record_change(name, args, result, ctx)
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        out: dict[str, Any] = {"ok": bool(result.get("success"))}
        if result.get("success"):
            out["task"] = _task_view(data) if data else None
        else:
            out["error"] = result.get("error")
    elif name in ("search_tasks", "get_task"):
        out = _task_result(result, ctx)
    else:
        out = {"ok": bool(result.get("success")), "data": result.get("data")} if result.get("success") else {"ok": False, "error": result.get("error")}

    payload = json.dumps(out, default=str)[:MAX_RESULT_CHARS]
    if spec.mutating:
        ctx.seen[key] = payload
    return payload


# --- the loop ----------------------------------------------------------------------------------------------


def _system_prompt(name: str, role: str) -> str:
    today = local_today()
    return TOOL_AGENT_PROMPT.format(
        today=today.isoformat(), weekday=today.strftime("%A"), timezone=settings.APP_TIMEZONE, name=name, role=role
    )


def _assistant_turn(message: Any) -> dict[str, Any]:
    calls = []
    for call in message.tool_calls or []:
        calls.append(
            {"id": call.id, "type": "function", "function": {"name": call.function.name, "arguments": call.function.arguments or "{}"}}
        )
    return {"role": "assistant", "content": message.content or "", "tool_calls": calls}


def build_reply(text: str, ctx: RunContext, stopped_early: Optional[str] = None) -> str:
    parts = [text] if text else []
    if ctx.changes:
        lines = [("• " if c["ok"] else "⚠️ ") + c["text"] for c in ctx.changes[:MAX_CHANGES + 2]]
        parts.append("*What changed*\n" + "\n".join(lines))
    if stopped_early:
        parts.append(stopped_early)
    return "\n\n".join(parts).strip() or EMPTY_REPLY


async def tool_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: work through the request with model-chosen tool calls."""
    user_id = str(state.get("user_id", ""))
    request = state.get("raw_message", "")

    def done(response: str, ctx: Optional[RunContext] = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "response": response,
            "response_type": "text",
            "card_data": None,
            "needs_confirmation": False,
            "tool_calls_made": list(ctx.tools_used) if ctx else list(state.get("tool_calls_made", [])),
        }
        if ctx and ctx.changes:
            result["actions_summary"] = [c["text"] for c in ctx.changes]
            if ctx.last_task_id and sum(1 for c in ctx.changes if c["ok"]) == 1:
                result["referenced_task_id"] = ctx.last_task_id
        return result

    if not llm_available():
        return done(BUSY_REPLY)

    async with get_tool_session() as db:
        from uuid import UUID

        try:
            user = await user_crud.get_user_by_id(db, UUID(user_id))
        except ValueError:
            user = None
    if user is None or not user.is_active:
        return done("I couldn't confirm who is asking, so I haven't done anything.")

    ctx = RunContext(user_id=user_id)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(user.display_name, user.role)},
        {"role": "user", "content": request},
    ]
    deadline = time.monotonic() + RUN_BUDGET_SECONDS
    final_text = ""
    stopped: Optional[str] = None

    for _ in range(MAX_STEPS):
        remaining = deadline - time.monotonic()
        if remaining < 2.0:
            stopped = "I ran out of time before finishing. Ask me again and I'll pick up where this left off."
            break
        message = await call_llm_with_tools(messages, TOOL_SCHEMAS, timeout=min(settings.LLM_TIMEOUT_SECONDS, remaining))
        if message is None:
            if not ctx.changes and not ctx.tools_used:
                return done(BUSY_REPLY)
            stopped = "The AI became busy before I could finish, so some of this may still be undone."
            break
        if not message.tool_calls:
            final_text = clean_reply(message.content)
            break
        messages.append(_assistant_turn(message))
        for call in message.tool_calls:
            output = await run_tool_call(call.function.name, call.function.arguments, ctx)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.function.name, "content": output})
    else:
        stopped = "This needed more steps than I can do in one go. Ask me to continue and I'll carry on."

    return done(build_reply(final_text, ctx, stopped), ctx)
