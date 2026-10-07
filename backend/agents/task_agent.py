"""Task Management Agent: Handles CRUD actions, searches, and card responses."""

from typing import Any
from agents.intents import Intent
from agents.state import AgentState
from tools.format_tools import format_task_card, format_task_list_text
from tools.task_tools import (
    complete_task,
    create_task,
    get_task_by_id,
    get_user_tasks,
    search_tasks,
    update_task,
)

HELP_TEXT = """*ORBIT AI Task Assistant* 🚀

Here are things you can ask me:
• *Create task:* "Create a high priority task for John to deploy frontend by Friday"
• *View tasks:* "Show my pending tasks" or "What are my overdue tasks?"
• *Plan day:* "What should I focus on today?"
• *Complete task:* "Mark the CRM deployment task as completed"
• *Update task:* "Change the API testing deadline to tomorrow"
• *Search:* "Search for database migration"
• *Delete task:* "Delete the old login page task"
"""


async def _handle_create_task(ctx: dict[str, Any], user_id: str, tools_used: list[str]) -> tuple[str, str, Any]:
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
        return f"❌ Failed to create task: {res.get('error')}", "text", None

    task_data = res.get("data", {})
    card = format_task_card(task_data)
    text = f"✅ Created Task #{task_data.get('id')}: *{task_data.get('title')}*"
    return text, "card", card


async def _handle_complete_task(ctx: dict[str, Any], user_id: str, tools_used: list[str]) -> tuple[str, str, Any]:
    """Resolve and complete a task."""
    task_id = ctx.get("task_id")
    if not task_id and ctx.get("title_hint"):
        tools_used.append("search_tasks")
        s_res = await search_tasks.ainvoke({"query": ctx.get("title_hint")})
        if s_res.get("success") and s_res.get("data"):
            task_id = s_res["data"][0].get("id")

    if not task_id:
        tools_used.append("get_user_tasks")
        u_res = await get_user_tasks.ainvoke({"user_id": user_id, "status": "TODO"})
        if u_res.get("success") and u_res.get("data"):
            task_id = u_res["data"][0].get("id")

    if not task_id:
        return "❌ Could not find the task to complete. Please provide the task name or ID.", "text", None

    tools_used.append("complete_task")
    c_res = await complete_task.ainvoke({"task_id": task_id, "completed_by_id": user_id})
    if not c_res.get("success"):
        return f"❌ Failed to complete task: {c_res.get('error')}", "text", None

    task_data = c_res.get("data", {})
    return f"🎉 Task #{task_data.get('id')} (*{task_data.get('title')}*) marked as completed!", "text", None


async def _handle_list_or_search(intent: str, ctx: dict[str, Any], user_id: str, raw_msg: str, tools_used: list[str]) -> tuple[str, str, Any]:
    """Handle listing user tasks or full-text searching."""
    if intent == Intent.SEARCH_TASKS.value:
        q = ctx.get("title_hint") or raw_msg
        tools_used.append("search_tasks")
        res = await search_tasks.ainvoke({"query": q})
        title = f"Search Results for '{q}'"
    else:
        tools_used.append("get_user_tasks")
        res = await get_user_tasks.ainvoke({"user_id": user_id})
        title = "Your Active Tasks"

    if not res.get("success"):
        return f"❌ Failed to retrieve tasks: {res.get('error')}", "text", None

    tasks = res.get("data", [])
    text = format_task_list_text(tasks, title=title)
    return text, "text", None


async def task_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Executes task operations based on intent."""
    intent = state.get("intent", Intent.UNKNOWN.value)
    ctx = state.get("task_context", {})
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    if intent == Intent.CREATE_TASK.value:
        resp_text, resp_type, card_data = await _handle_create_task(ctx, user_id, tools_used)
    elif intent == Intent.COMPLETE_TASK.value:
        resp_text, resp_type, card_data = await _handle_complete_task(ctx, user_id, tools_used)
    elif intent in (Intent.GET_MY_TASKS.value, Intent.SEARCH_TASKS.value):
        resp_text, resp_type, card_data = await _handle_list_or_search(intent, ctx, user_id, state.get("raw_message", ""), tools_used)
    elif intent == Intent.HELP.value:
        resp_text, resp_type, card_data = HELP_TEXT, "text", None
    else:
        resp_text = "I didn't quite catch that. You can ask me to create tasks, view pending tasks, plan your day, or type 'help'."
        resp_type, card_data = "text", None

    return {
        "response": resp_text,
        "response_type": resp_type,
        "card_data": card_data,
        "tool_calls_made": tools_used,
    }
