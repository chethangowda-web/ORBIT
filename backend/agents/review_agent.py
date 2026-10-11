from datetime import datetime, timedelta, timezone
from typing import Any
from agents.state import AgentState
from auth.rbac import is_manager
from crud import users as user_crud
from tools.base import get_tool_session
from tools.task_tools import delete_task, get_task_by_id, search_tasks


# A delete confirmation answers the question that was just asked, not one from hours ago.
PENDING_CONFIRMATION_TTL = timedelta(minutes=10)


def _pending_expired(pending: dict[str, Any]) -> bool:
    try:
        created = datetime.fromisoformat(str(pending.get("created_at")))
    except (TypeError, ValueError):
        return True  # an unreadable timestamp cannot be trusted
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - created > PENDING_CONFIRMATION_TTL


async def _caller_may_delete(user_id: str) -> bool:
    """Only managers and admins can delete; checked before any task is disclosed."""
    import uuid as _uuid

    try:
        async with get_tool_session() as db:
            user = await user_crud.get_user_by_id(db, _uuid.UUID(str(user_id)))
    except (ValueError, TypeError):
        return False
    return bool(user and user.is_active and is_manager(user))


async def _resolve_target_task(state: AgentState, tools_used: list[str]) -> tuple[Any, Any, list[str]]:
    """Resolves task ID and title for destructive action.

    Returns (task_id, title, ambiguous_titles); the last item is non-empty when several tasks
    match and the user has to say which one."""
    ctx = state.get("task_context", {})
    raw_msg = state.get("raw_message", "")
    task_id = ctx.get("task_id") or state.get("referenced_task_id")
    if task_id:
        tools_used.append("get_task_by_id")
        t_res = await get_task_by_id.ainvoke({"task_id": task_id, "viewer_id": state.get("user_id")})
        if t_res.get("success"):
            return task_id, t_res.get("data", {}).get("title", "Untitled"), []

    query = ctx.get("title_hint") or raw_msg
    tools_used.append("search_tasks")
    s_res = await search_tasks.ainvoke(
        {"query": query, "include_completed": True, "viewer_id": state.get("user_id")}
    )
    matches = (s_res.get("data") or []) if s_res.get("success") else []
    if len(matches) > 1:
        exact = [m for m in matches if str(m.get("title", "")).strip().lower() == str(query).strip().lower()]
        if len(exact) == 1:
            matches = exact
        else:
            return None, None, [str(m.get("title", "Untitled")) for m in matches[:5]]
    if matches:
        return matches[0].get("id"), matches[0].get("title"), []
    return None, None, []


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

        if _pending_expired(pending):
            return {
                "response": "⌛ That confirmation has expired. Please ask me to delete the task again.",
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

    # First turn: refuse early so employees are never shown a task they cannot delete
    if not await _caller_may_delete(user_id):
        return {
            "response": "🚫 Only managers and admins can delete tasks. Ask a manager, or mark the task complete or cancelled instead.",
            "response_type": "text",
            "needs_confirmation": False,
            "pending_confirmation": None,
            "tool_calls_made": tools_used,
        }

    # Identify target and establish pending confirmation state
    task_id, task_title, ambiguous = await _resolve_target_task(state, tools_used)
    if ambiguous:
        listing = "\n".join(f"• {title}" for title in ambiguous)
        return {
            "response": f"🤔 Multiple tasks match. Which one should I delete?\n{listing}\nTell me the exact title or ID.",
            "response_type": "text",
            "needs_confirmation": False,
            "pending_confirmation": None,
            "tool_calls_made": tools_used,
        }
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
