"""Recommendation Agent: Generates workload insights, overdue alerts, and productivity tips with LLM reasoning and deterministic fallback."""

import json
from typing import Any
from agents.intents import Intent
from agents.prompts import RECOMMENDATION_PROMPT
from agents.state import AgentState
from auth.rbac import is_manager
from crud import users as user_crud
from services.assignment import rank_assignees
from services.llm import call_llm
from tools.base import get_tool_session
from tools.format_tools import due_phrase, friendly
from tools.analytics_tools import get_task_stats
from tools.task_tools import get_overdue_tasks
from tools.user_tools import get_team_workload


def _format_overdue_response(tasks: list[dict[str, Any]]) -> str:
    """Formats overdue tasks alert (deterministic fallback)."""
    if not tasks:
        return "✅ *Great news!* You currently have no overdue tasks."

    lines = [f"⚠️ *Late tasks ({len(tasks)})*", "These are past their due date:\n"]
    for t in tasks:
        p_val = str(t.get('priority', 'MEDIUM')).split('.')[-1]
        lines.append(f"• *{t.get('title')}* ({friendly(p_val)} priority, {due_phrase(t.get('due_date'))})")
    lines.append("\n💡 Tell me if any of these are done, or if a due date should move.")
    return "\n".join(lines)


def _format_recommendations_response(stats: dict[str, Any], workload: list[dict[str, Any]]) -> str:
    """Formats overall team and personal recommendations (deterministic fallback)."""
    lines = ["📊 *How things are going*", ""]

    total = stats.get("total_tasks", 0)
    completed = stats.get("completed_tasks", 0)
    overdue = stats.get("overdue_tasks", 0)
    rate = stats.get("completion_rate", 0.0)

    lines.append(f"• *Tasks finished:* {rate * 100:.0f}% ({completed} of {total})")
    if overdue > 0:
        lines.append(f"• *Late:* {overdue} task{'s' if overdue != 1 else ''} need attention.")

    if workload:
        busiest = max(workload, key=lambda w: w.get("assigned_tasks", 0), default=None)
        if busiest and busiest.get("assigned_tasks", 0) > 3:
            lines.append(f"• *Busy:* {busiest.get('display_name')} has {busiest.get('assigned_tasks')} tasks. Consider handing some to a teammate.")

    lines.append("\n💡 *Quick wins:*")
    lines.append("1. Finish the small items first thing in the morning.")
    lines.append("2. Give high-priority work realistic due dates.")
    return "\n".join(lines)


async def _suggest_assignee(state: AgentState, user_id: str, tools_used: list[str]) -> dict[str, Any]:
    """Who has room for more work: plain arithmetic on real task counts, so no AI request is needed."""
    import uuid

    tools_used.append("suggest_assignee")
    async with get_tool_session() as db:
        try:
            asker = await user_crud.get_user_by_id(db, uuid.UUID(str(user_id)))
        except ValueError:
            asker = None
        if asker is None or not is_manager(asker):
            text = "🚫 Only managers and admins can hand work to other people, so I can't compare workloads for you. Ask your manager, or tell me what you want to do with your own tasks."
            return {"response": text, "response_type": "text", "card_data": None, "tool_calls_made": tools_used}
        ranked = await rank_assignees(db, limit=3)

    if not ranked:
        text = "I couldn't find anyone to suggest right now."
    else:
        best, rest = ranked[0], ranked[1:]
        hint = (state.get("task_context") or {}).get("title_hint")
        subject = f" for *{hint}*" if hint else ""
        text = f"🧭 *{best.name}* looks best placed{subject}: {best.reason}."
        if rest:
            text += "\nNext: " + "; ".join(f"*{c.name}* ({c.reason})" for c in rest) + "."
        text += f"\nSay *assign it to {best.name.split(' ')[0]}* to hand a task over."
    return {"response": text, "response_type": "text", "card_data": None, "tool_calls_made": tools_used}


async def recommendation_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Generates overdue alerts and productivity insights with LLM reasoning and factual fallback."""
    intent = state.get("intent", Intent.GET_RECOMMENDATIONS.value)
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    if intent == Intent.SUGGEST_ASSIGNEE.value:
        return await _suggest_assignee(state, user_id, tools_used)

    if intent == Intent.GET_OVERDUE_TASKS.value:
        tools_used.append("get_overdue_tasks")
        res = await get_overdue_tasks.ainvoke({"user_id": user_id})
        overdue_tasks = res.get("data", []) if res.get("success") else []

        if not overdue_tasks:
            return {
                "response": "✅ *Great news!* You currently have no overdue tasks.",
                "response_type": "text",
                "card_data": None,
                "tool_calls_made": tools_used,
            }

        fallback_text = _format_overdue_response(overdue_tasks)
        messages = [
            {"role": "system", "content": RECOMMENDATION_PROMPT},
            {
                "role": "user",
                "content": f"The user has the following overdue tasks in the database:\n{json.dumps(overdue_tasks, indent=2, default=str)}\n\nProvide an alert explaining which tasks are most urgent and suggesting actionable remediation steps.",
            },
        ]
        llm_resp = await call_llm(messages=messages, temperature=0.2)
        response_text = llm_resp.strip() if (llm_resp and isinstance(llm_resp, str) and len(llm_resp.strip()) > 20) else fallback_text

    else:
        tools_used.extend(["get_task_stats", "get_team_workload"])
        stats_res = await get_task_stats.ainvoke({"viewer_id": user_id})
        # Team-wide workload is manager/admin data; for everyone else the tool refuses
        # and the insights fall back to the caller's own numbers.
        workload_res = await get_team_workload.ainvoke({"viewer_id": user_id})

        stats_data = stats_res.get("data", {}) if stats_res.get("success") else {}
        workload_data = workload_res.get("data", []) if workload_res.get("success") else []
        fallback_text = _format_recommendations_response(stats_data, workload_data)

        messages = [
            {"role": "system", "content": RECOMMENDATION_PROMPT},
            {
                "role": "user",
                "content": f"Here is the authentic project analytics and team workload data:\nTask Stats: {json.dumps(stats_data, indent=2, default=str)}\nTeam Workload: {json.dumps(workload_data, indent=2, default=str)}\n\nSynthesize concise, high-impact recommendations to improve team velocity and reduce bottlenecks.",
            },
        ]
        llm_resp = await call_llm(messages=messages, temperature=0.2)
        response_text = llm_resp.strip() if (llm_resp and isinstance(llm_resp, str) and len(llm_resp.strip()) > 20) else fallback_text

    return {
        "response": response_text,
        "response_type": "text",
        "card_data": None,
        "tool_calls_made": tools_used,
    }

