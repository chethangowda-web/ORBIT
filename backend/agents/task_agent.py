"""Task Management Agent: Handles CRUD actions, searches, updates, and card responses."""

import re
from typing import Any, Optional
from agents.intents import Intent
from agents.state import AgentState
from tools.format_tools import format_task_card, format_task_list_card, format_task_list_text
from tools.task_tools import (
    complete_task,
    create_task,
    get_task_by_id,
    get_user_tasks,
    search_tasks,
    update_task,
)
from services.duplicate_check import check_for_duplicates, describe
from services.undo import format_undo, undo_last_changes
from tools.format_tools import friendly
from tools.user_tools import get_all_users

HELP_TEXT = """*What ORBIT can do* 🚀

Just tell me in your own words, for example:
• *Add a task:* "Create a high priority task for John to prepare the client deck by Friday"
• *See your work:* "Show my tasks" or "What is overdue?"
• *Plan your day:* "What should I focus on today?"
• *Finish a task:* "Mark the budget report as done"
• *Change a task:* "Make it high priority" or "Move the deadline to tomorrow"
• *Hand over a task:* "Assign that to Sarah"
• *Find a task:* "Search for budget report"
• *Remove a task:* "Delete the old brochure task" (I will ask you to confirm first)
• *Changed your mind:* "Undo that" reverses what I just did in chat
"""


def greeting_reply(raw_message: str, first_name: str = "") -> str:
    """Friendly reply to hello/thanks that points at what ORBIT can do."""
    text = raw_message.strip().lower()
    if re.match(r"^(thanks|thank you|thx|ty|cheers)\b", text):
        return "You're welcome! Anything else I can help with? Try *plan my day* or */tasks*."
    name = f", {first_name}" if first_name else ""
    return (
        f"👋 Hi{name}! I'm ORBIT, your task assistant.\n"
        "Try *plan my day*, */tasks*, */overdue*, or tell me what to do, for example "
        "*create a task to review the PR by Friday*. Type *help* for everything I can do."
    )


async def _handle_create_task(
    ctx: dict[str, Any], user_id: str, tools_used: list[str], extra: Optional[dict[str, Any]] = None
) -> tuple[str, str, Any, Any]:
    """Execute task creation and generate response payload.

    The very same task for the same person is not added twice: ORBIT says so and waits for "create it
    anyway" (kept in `extra["pending_duplicate"]`). A merely similar task is created, with a heads-up."""
    title = ctx.get("title") or "New Task"
    similar_note = ""
    if not ctx.get("allow_duplicate"):
        check = await check_for_duplicates(user_id, title, ctx.get("assignee_name"))
        if check.blocking:
            if extra is not None:
                extra["pending_duplicate"] = {k: v for k, v in ctx.items() if k != "allow_duplicate"}
            return (
                f"👀 {describe(check.blocking)} is already on the list, so I didn't add another. "
                "Say *create it anyway* if you want a second one.",
                "text",
                None,
                check.blocking["id"],
            )
        if check.similar:
            similar_note = f"\n\n👀 Heads-up: there is already a similar task, {describe(check.similar[0])}."
    priority = ctx.get("priority") or "MEDIUM"
    assignee = ctx.get("assignee_name")
    due_date = ctx.get("due_date")

    tools_used.append("create_task")
    res = await create_task.ainvoke({
        "title": title,
        "priority": priority,
        "assignee_name": assignee,
        "due_date": due_date,
        "created_by_id": user_id,
    })

    if not res.get("success"):
        return f"❌ Failed to create task: {res.get('error')}", "text", None, None

    task_data = res.get("data", {})
    card = format_task_card(task_data)
    text = f"✅ Created *{task_data.get('title')}*{similar_note}"
    return text, "card", card, str(task_data.get("id")) if task_data.get("id") else None


async def _handle_update_task(ctx: dict[str, Any], user_id: str, state_ref_id: Any, raw_msg: str, tools_used: list[str]) -> tuple[str, str, Any, Any]:
    """Resolve target task and execute update operations (priority, deadline, assignee, status)."""
    task_id = ctx.get("task_id") or state_ref_id

    if not task_id and ctx.get("title_hint"):
        tools_used.append("search_tasks")
        s_res = await search_tasks.ainvoke({"query": ctx.get("title_hint"), "viewer_id": user_id})
        if s_res.get("success") and s_res.get("data"):
            matches = s_res["data"]
            if len(matches) == 1:
                task_id = matches[0].get("id")
            elif len(matches) > 1:
                return (
                    f"🤔 Multiple tasks match '{ctx.get('title_hint')}'. Please specify the exact task ID or unique title.",
                    "text",
                    None,
                    None,
                )

    if not task_id:
        return (
            "🤔 Which task do you mean? Tell me its name, for example: 'Make the budget report high priority'.",
            "text",
            None,
            None,
        )

    tools_used.append("update_task")
    update_payload: dict[str, Any] = {
        "task_id": task_id,
        "updated_by_id": user_id,
    }
    if ctx.get("priority"):
        update_payload["priority"] = ctx.get("priority")
    if ctx.get("due_date"):
        update_payload["due_date"] = ctx.get("due_date")
    if ctx.get("assignee_name"):
        update_payload["assignee_name"] = ctx.get("assignee_name")
    if ctx.get("title"):
        update_payload["title"] = ctx.get("title")

    u_res = await update_task.ainvoke(update_payload)
    if not u_res.get("success"):
        return f"❌ Failed to update task: {u_res.get('error')}", "text", None, str(task_id)

    task_data = dict(u_res.get("data", {}))
    changes = []
    if ctx.get("priority"):
        p_val = str(task_data.get("priority", "")).split(".")[-1]
        task_data["priority"] = p_val
        changes.append(f"priority is now *{friendly(p_val)}*")
    if ctx.get("due_date"):
        changes.append(f"due date is now {task_data.get('due_date')}")
    if ctx.get("assignee_name"):
        changes.append(f"it is now with *{ctx.get('assignee_name')}*")
    changes_str = ", ".join(changes) if changes else "details saved"

    card = format_task_card(task_data)
    return (
        f"✏️ Updated *{task_data.get('title')}*: {changes_str}.",
        "card",
        card,
        str(task_data.get("id")),
    )


async def _handle_get_task_detail(ctx: dict[str, Any], user_id: str, state_ref_id: Any, raw_msg: str, tools_used: list[str]) -> tuple[str, str, Any, Any]:
    """Retrieve full task details including history and assignee."""
    task_id = ctx.get("task_id") or state_ref_id
    if not task_id and ctx.get("title_hint"):
        tools_used.append("search_tasks")
        s_res = await search_tasks.ainvoke({"query": ctx.get("title_hint"), "viewer_id": user_id})
        if s_res.get("success") and s_res.get("data"):
            task_id = s_res["data"][0].get("id")

    if not task_id:
        return "🤔 Which task do you mean? Tell me its name.", "text", None, None

    tools_used.append("get_task_by_id")
    res = await get_task_by_id.ainvoke({"task_id": task_id, "viewer_id": user_id})
    if not res.get("success"):
        return f"❌ Task not found: {res.get('error')}", "text", None, None

    task_data = res.get("data", {})
    card = format_task_card(task_data)
    return (
        f"📌 *{task_data.get('title')}* is {friendly(task_data.get('status'))}.",
        "card",
        card,
        str(task_data.get("id")),
    )


async def _handle_complete_task(ctx: dict[str, Any], user_id: str, state_ref_id: Any, tools_used: list[str]) -> tuple[str, str, Any, Any]:
    """Resolve and complete a task."""
    task_id = ctx.get("task_id") or state_ref_id
    if not task_id and ctx.get("title_hint"):
        tools_used.append("search_tasks")
        s_res = await search_tasks.ainvoke({"query": ctx.get("title_hint"), "viewer_id": user_id})
        matches = s_res.get("data") or [] if s_res.get("success") else []
        if len(matches) == 1:
            task_id = matches[0].get("id")
        elif len(matches) > 1:
            names = ", ".join(f"*{m.get('title')}*" for m in matches[:5])
            return (
                f"🤔 Several tasks match '{ctx.get('title_hint')}': {names}. Which one should I complete?",
                "text",
                None,
                None,
            )

    if not task_id:
        # Never guess: completing the wrong task is hard to notice and undo.
        return (
            "🤔 Which task should I complete? Give me its title or ID (for example: 'complete the CRM deployment task').",
            "text",
            None,
            None,
        )

    tools_used.append("complete_task")
    c_res = await complete_task.ainvoke({"task_id": task_id, "completed_by_id": user_id})
    if not c_res.get("success"):
        return f"❌ Failed to complete task: {c_res.get('error')}", "text", None, None

    task_data = c_res.get("data", {})
    return f"🎉 *{task_data.get('title')}* marked as completed!", "text", None, str(task_data.get("id")) if task_data.get("id") else None


async def _handle_list_or_search(intent: str, ctx: dict[str, Any], user_id: str, raw_msg: str, tools_used: list[str]) -> tuple[str, str, Any]:
    """List or search tasks. Returns (text, response_type, card_data).

    The text always holds the full list so the dashboard and plain-text channels work;
    Google Chat additionally gets an interactive card."""
    if intent == Intent.SEARCH_TASKS.value:
        q = ctx.get("title_hint") or raw_msg
        tools_used.append("search_tasks")
        res = await search_tasks.ainvoke({"query": q, "viewer_id": user_id})
        title = f"Search Results for '{q}'"
    else:
        tools_used.append("get_user_tasks")
        res = await get_user_tasks.ainvoke({"user_id": user_id})
        title = "Your Active Tasks"

    if not res.get("success"):
        return f"❌ Failed to retrieve tasks: {res.get('error')}", "text", None

    tasks = res.get("data", [])
    text = format_task_list_text(tasks, title=title)
    if tasks:
        return text, "card", format_task_list_card(tasks, title=title)
    return text, "text", None


async def task_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Executes task operations based on intent."""
    intent = state.get("intent", Intent.UNKNOWN.value)
    ctx = state.get("task_context", {})
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))
    ref_task_id = state.get("referenced_task_id")
    extra: dict[str, Any] = {}

    if state.get("response") and (state.get("pending_confirmation") or {}).get("status") == "CANCELLED":
        resp_text = state.get("response", "❌ Action cancelled.")
        resp_type, card_data = "text", None
    elif intent == Intent.CREATE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_create_task(ctx, user_id, tools_used, extra)
    elif intent == Intent.UPDATE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_update_task(ctx, user_id, ref_task_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.GET_TASK_DETAIL.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_get_task_detail(ctx, user_id, ref_task_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.COMPLETE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_complete_task(ctx, user_id, ref_task_id, tools_used)
    elif intent in (Intent.GET_MY_TASKS.value, Intent.SEARCH_TASKS.value):
        resp_text, resp_type, card_data = await _handle_list_or_search(intent, ctx, user_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.UNDO_LAST.value:
        tools_used.append("undo_last_changes")
        resp_text, resp_type, card_data = format_undo(await undo_last_changes(user_id)), "text", None
    elif intent == Intent.HELP.value:
        resp_text, resp_type, card_data = HELP_TEXT, "text", None
    elif intent == Intent.GREETING.value:
        resp_text, resp_type, card_data = greeting_reply(state.get("raw_message", ""), state.get("user_first_name", "")), "text", None
    else:
        resp_text = "I didn't quite catch that. You can ask me to create tasks, view pending tasks, update priorities/deadlines, plan your day, or type 'help'."
        resp_type, card_data = "text", None

    result: dict[str, Any] = {
        **extra,
        "response": resp_text,
        "response_type": resp_type,
        "card_data": card_data,
        "tool_calls_made": tools_used,
    }
    if ref_task_id:
        result["referenced_task_id"] = str(ref_task_id)
    return result

