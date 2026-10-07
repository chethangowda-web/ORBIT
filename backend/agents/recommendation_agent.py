"""Recommendation Agent: Generates workload insights, overdue alerts, and productivity tips."""

from typing import Any
from agents.intents import Intent
from agents.state import AgentState
from tools.analytics_tools import get_task_stats
from tools.task_tools import get_overdue_tasks
from tools.user_tools import get_team_workload


def _format_overdue_response(tasks: list[dict[str, Any]]) -> str:
    """Formats overdue tasks alert."""
    if not tasks:
        return "✅ *Great news!* You currently have no overdue tasks."

    lines = [f"⚠️ *Overdue Tasks Alert ({len(tasks)} items)*", "These tasks are past their deadline:\n"]
    for t in tasks:
        lines.append(f"• *{t.get('title')}* `[{t.get('priority')}]` — Due: {t.get('due_date')}")
    lines.append("\n💡 *Suggestion:* Re-prioritize or re-assign these tasks to avoid bottlenecks.")
    return "\n".join(lines)


def _format_recommendations_response(stats: dict[str, Any], workload: list[dict[str, Any]]) -> str:
    """Formats overall team and personal recommendations."""
    lines = ["📊 *Productivity Insights & Recommendations*", ""]

    total = stats.get("total_tasks", 0)
    completed = stats.get("completed_tasks", 0)
    overdue = stats.get("overdue_tasks", 0)
    rate = stats.get("completion_rate", 0.0)

    lines.append(f"• *Task Completion Rate:* {rate:.1f}% ({completed}/{total} tasks)")
    if overdue > 0:
        lines.append(f"• *Overdue Items:* {overdue} tasks need attention.")

    if workload:
        busiest = max(workload, key=lambda w: w.get("active_tasks", 0), default=None)
        if busiest and busiest.get("active_tasks", 0) > 3:
            lines.append(f"• *Team Load Alert:* {busiest.get('user_name')} has {busiest.get('active_tasks')} active tasks. Consider rebalancing assignments.")

    lines.append("\n💡 *Actionable Advice:*")
    lines.append("1. Close out quick TODO items first thing in the morning.")
    lines.append("2. Set realistic due dates for high-priority initiatives.")
    return "\n".join(lines)


async def recommendation_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Generates overdue alerts and productivity insights."""
    intent = state.get("intent", Intent.GET_RECOMMENDATIONS.value)
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    if intent == Intent.GET_OVERDUE_TASKS.value:
        tools_used.append("get_overdue_tasks")
        res = await get_overdue_tasks.ainvoke({"user_id": user_id})
        overdue_tasks = res.get("data", []) if res.get("success") else []
        response_text = _format_overdue_response(overdue_tasks)
    else:
        tools_used.extend(["get_task_stats", "get_team_workload"])
        stats_res = await get_task_stats.ainvoke({"user_id": user_id})
        workload_res = await get_team_workload.ainvoke({})

        stats_data = stats_res.get("data", {}) if stats_res.get("success") else {}
        workload_data = workload_res.get("data", []) if workload_res.get("success") else []
        response_text = _format_recommendations_response(stats_data, workload_data)

    return {
        "response": response_text,
        "response_type": "text",
        "card_data": None,
        "tool_calls_made": tools_used,
    }
