"""Review and Validation Agent: Implements HITL safety checks for destructive actions."""

from typing import Any
from agents.state import AgentState
from tools.task_tools import delete_task, get_task_by_id, search_tasks


async def _resolve_target_task(ctx: dict[str, Any], raw_msg: str, tools_used: list[str]) -> tuple[Any, Any]:
    """Resolves task ID and title for destructive action."""
    task_id = ctx.get("task_id")
    if task_id:
        tools_used.append("get_task_by_id")
        t_res = await get_task_by_id.ainvoke({"task_id": task_id})
        if t_res.get("success"):
            return task_id, t_res.get("data", {}).get("title", "Untitled")

    query = ctx.get("title_hint") or raw_msg
    tools_used.append("search_tasks")
    s_res = await search_tasks.ainvoke({"query": query})
    if s_res.get("success") and s_res.get("data"):
        matched = s_res["data"][0]
        return matched.get("id"), matched.get("title")
    return None, None


async def review_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Enforces HITL confirmation for deletion and sensitive actions."""
    ctx = state.get("task_context", {})
    user_id = state.get("user_id", "")
    confirmed = state.get("confirmed", False)
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    task_id, task_title = await _resolve_target_task(ctx, state.get("raw_message", ""), tools_used)
    if not task_id:
        return {
            "response": "❌ Could not find the task to delete. Please specify the task title or ID.",
            "response_type": "text",
            "needs_confirmation": False,
            "tool_calls_made": tools_used,
        }

    if not confirmed:
        prompt_text = f"⚠️ *Confirmation Required*\nAre you sure you want to delete Task #{task_id} (*{task_title}*)?\nReply 'yes' or click Confirm."
        return {
            "response": prompt_text,
            "response_type": "confirmation_dialog",
            "needs_confirmation": True,
            "referenced_task_id": str(task_id),
            "tool_calls_made": tools_used,
        }

    tools_used.append("delete_task")
    del_res = await delete_task.ainvoke({"task_id": task_id, "deleted_by_id": user_id})
    if not del_res.get("success"):
        return {
            "response": f"❌ Failed to delete task: {del_res.get('error')}",
            "response_type": "text",
            "needs_confirmation": False,
            "tool_calls_made": tools_used,
        }

    return {
        "response": f"🗑️ Task #{task_id} (*{task_title}*) has been successfully deleted.",
        "response_type": "text",
        "needs_confirmation": False,
        "tool_calls_made": tools_used,
    }
