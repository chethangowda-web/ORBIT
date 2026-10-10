from datetime import datetime, timezone
from typing import Any
from agents.state import AgentState
from tools.task_tools import delete_task, get_task_by_id, search_tasks


async def _resolve_target_task(state: AgentState, tools_used: list[str]) -> tuple[Any, Any]:
    """Resolves task ID and title for destructive action."""
    ctx = state.get("task_context", {})
    raw_msg = state.get("raw_message", "")
    task_id = ctx.get("task_id") or state.get("referenced_task_id")
    if task_id:
        tools_used.append("get_task_by_id")
        t_res = await get_task_by_id.ainvoke({"task_id": task_id})
        if t_res.get("success"):
            return task_id, t_res.get("data", {}).get("title", "Untitled")

    query = ctx.get("title_hint") or raw_msg
    tools_used.append("search_tasks")
    s_res = await search_tasks.ainvoke({"query": query, "include_completed": True})
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
    thread_id = str(state.get("thread_id", ""))
    pending = state.get("pending_confirmation")

    # If already confirmed, validate against pending_confirmation contract
    if confirmed:
        if not pending or pending.get("status") != "PENDING":
            return {
                "response": "❌ No valid pending action to confirm, or the action was already consumed or cancelled.",
                "response_type": "text",
                "needs_confirmation": False,
                "pending_confirmation": None,
                "tool_calls_made": tools_used,
            }

        # Check authenticated user and thread match
        if pending.get("user_id") != str(user_id) or pending.get("thread_id") != thread_id:
            return {
                "response": "❌ Security verification failed: confirmation does not match the authenticated session.",
                "response_type": "text",
                "needs_confirmation": False,
                "pending_confirmation": None,
                "tool_calls_made": tools_used,
            }

        target_task_id = pending.get("task_id")
        target_title = pending.get("task_title", "Task")

        # Mark confirmation as consumed to prevent replay attacks
        pending_updated = dict(pending)
        pending_updated["status"] = "CONSUMED"
        pending_updated["consumed_at"] = datetime.now(timezone.utc).isoformat()

        tools_used.append("delete_task")
        del_res = await delete_task.ainvoke({"task_id": target_task_id, "deleted_by_id": user_id})
        if not del_res.get("success"):
            return {
                "response": f"❌ Failed to delete task: {del_res.get('error')}",
                "response_type": "text",
                "needs_confirmation": False,
                "pending_confirmation": pending_updated,
                "tool_calls_made": tools_used,
            }

        return {
            "response": f"🗑️ Task #{target_task_id} (*{target_title}*) has been successfully deleted.",
            "response_type": "text",
            "needs_confirmation": False,
            "pending_confirmation": pending_updated,
            "tool_calls_made": tools_used,
        }

    # First turn: Identify target and establish pending confirmation state
    task_id, task_title = await _resolve_target_task(state, tools_used)
    if not task_id:
        return {
            "response": "❌ Could not find the task to delete. Please specify the task title or ID.",
            "response_type": "text",
            "needs_confirmation": False,
            "pending_confirmation": None,
            "tool_calls_made": tools_used,
        }

    new_pending = {
        "action": "DELETE_TASK",
        "task_id": str(task_id),
        "task_title": task_title,
        "user_id": str(user_id),
        "thread_id": thread_id,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    prompt_text = f"⚠️ *Confirmation Required*\nAre you sure you want to delete Task #{task_id} (*{task_title}*)?\nReply 'yes' or click Confirm."
    return {
        "response": prompt_text,
        "response_type": "confirmation_dialog",
        "needs_confirmation": True,
        "pending_confirmation": new_pending,
        "referenced_task_id": str(task_id),
        "tool_calls_made": tools_used,
    }
