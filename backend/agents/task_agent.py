"""Task Management Agent: Handles CRUD actions, searches, updates, and card responses."""

from typing import Any
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
from tools.user_tools import get_all_users

HELP_TEXT = """*ORBIT AI Task Assistant* 🚀

Here are things you can ask me:
• *Create task:* "Create a high priority task for John to deploy frontend by Friday"
• *View tasks:* "Show my pending tasks" or "What are my overdue tasks?"
• *Plan day:* "What should I focus on today?"
• *Complete task:* "Mark the CRM deployment task as completed"
• *Update task:* "Make it high priority" or "Change the API testing deadline to tomorrow"
• *Assign task:* "Assign that to Sarah"
• *Search:* "Search for database migration"
• *Delete task:* "Delete the old login page task"
"""


async def _handle_create_task(ctx: dict[str, Any], user_id: str, tools_used: list[str]) -> tuple[str, str, Any, Any]:
    """Execute task creation and generate response payload."""
    title = ctx.get("title") or "New Task"
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
    text = f"✅ Created Task #{task_data.get('id')}: *{task_data.get('title')}*"
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
        tools_used.append("get_user_tasks")
        u_tasks_res = await get_user_tasks.ainvoke({"user_id": user_id, "status": ["TODO", "IN_PROGRESS"]})
        if u_tasks_res.get("success") and u_tasks_res.get("data"):
            active_tasks = u_tasks_res["data"]
            if len(active_tasks) == 1:
                task_id = active_tasks[0].get("id")

    if not task_id:
        return (
            "🤔 Which task would you like to update? Please specify the task title or ID (e.g. 'Make Task #123 high priority').",
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
        changes.append(f"priority → `[{p_val}]`")
    if ctx.get("due_date"):
        changes.append(f"deadline → {task_data.get('due_date')}")
    if ctx.get("assignee_name"):
        changes.append(f"assignee → *{ctx.get('assignee_name')}*")
    changes_str = ", ".join(changes) if changes else "details updated"

    card = format_task_card(task_data)
    return (
        f"✏️ Updated Task #{task_data.get('id')} (*{task_data.get('title')}*): {changes_str}.",
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
        return "🤔 Which task would you like to view? Please specify the task title or ID.", "text", None, None

    tools_used.append("get_task_by_id")
    res = await get_task_by_id.ainvoke({"task_id": task_id, "viewer_id": user_id})
    if not res.get("success"):
        return f"❌ Task not found: {res.get('error')}", "text", None, None

    task_data = res.get("data", {})
    card = format_task_card(task_data)
    return (
        f"📌 Details for Task #{task_data.get('id')}: *{task_data.get('title')}* `[{task_data.get('status')}]`",
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
    return f"🎉 Task #{task_data.get('id')} (*{task_data.get('title')}*) marked as completed!", "text", None, str(task_data.get("id")) if task_data.get("id") else None


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

    if state.get("response") and (state.get("pending_confirmation") or {}).get("status") == "CANCELLED":
        resp_text = state.get("response", "❌ Action cancelled.")
        resp_type, card_data = "text", None
    elif intent == Intent.CREATE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_create_task(ctx, user_id, tools_used)
    elif intent == Intent.UPDATE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_update_task(ctx, user_id, ref_task_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.GET_TASK_DETAIL.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_get_task_detail(ctx, user_id, ref_task_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.COMPLETE_TASK.value:
        resp_text, resp_type, card_data, ref_task_id = await _handle_complete_task(ctx, user_id, ref_task_id, tools_used)
    elif intent in (Intent.GET_MY_TASKS.value, Intent.SEARCH_TASKS.value):
        resp_text, resp_type, card_data = await _handle_list_or_search(intent, ctx, user_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.HELP.value:
        resp_text, resp_type, card_data = HELP_TEXT, "text", None
    else:
        resp_text = "I didn't quite catch that. You can ask me to create tasks, view pending tasks, update priorities/deadlines, plan your day, or type 'help'."
        resp_type, card_data = "text", None

    result: dict[str, Any] = {
        "response": resp_text,
        "response_type": resp_type,
        "card_data": card_data,
        "tool_calls_made": tools_used,
    }
    if ref_task_id:
        result["referenced_task_id"] = str(ref_task_id)
    return result

