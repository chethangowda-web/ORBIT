"""Recommendation Agent: Generates workload insights, overdue alerts, and productivity tips with LLM reasoning and deterministic fallback."""

import json
from typing import Any
from agents.intents import Intent
from agents.prompts import RECOMMENDATION_PROMPT
from agents.state import AgentState
from services.llm import call_llm
from tools.analytics_tools import get_task_stats
from tools.task_tools import get_overdue_tasks
from tools.user_tools import get_team_workload


def _format_overdue_response(tasks: list[dict[str, Any]]) -> str:
    """Formats overdue tasks alert (deterministic fallback)."""
    if not tasks:
        return "✅ *Great news!* You currently have no overdue tasks."

    lines = [f"⚠️ *Overdue Tasks Alert ({len(tasks)} items)*", "These tasks are past their deadline:\n"]
    for t in tasks:
        p_val = str(t.get('priority', 'MEDIUM')).split('.')[-1]
        lines.append(f"• *{t.get('title')}* `[{p_val}]` — Due: {t.get('due_date')}")
    lines.append("\n💡 *Suggestion:* Re-prioritize or re-assign these tasks to avoid bottlenecks.")
    return "\n".join(lines)


def _format_recommendations_response(stats: dict[str, Any], workload: list[dict[str, Any]]) -> str:
    """Formats overall team and personal recommendations (deterministic fallback)."""
    lines = ["📊 *Productivity Insights & Recommendations*", ""]

    total = stats.get("total_tasks", 0)
    completed = stats.get("completed_tasks", 0)
    overdue = stats.get("overdue_tasks", 0)
    rate = stats.get("completion_rate", 0.0)

    lines.append(f"• *Task Completion Rate:* {rate:.1f}% ({completed}/{total} tasks)")
    if overdue > 0:
        lines.append(f"• *Overdue Items:* {overdue} tasks need attention.")

    if workload:
        busiest = max(workload, key=lambda w: w.get("assigned_tasks", 0), default=None)
        if busiest and busiest.get("assigned_tasks", 0) > 3:
            lines.append(f"• *Team Load Alert:* {busiest.get('display_name')} has {busiest.get('assigned_tasks')} assigned tasks. Consider rebalancing assignments.")

    lines.append("\n💡 *Actionable Advice:*")
    lines.append("1. Close out quick TODO items first thing in the morning.")
    lines.append("2. Set realistic due dates for high-priority initiatives.")
    return "\n".join(lines)


async def recommendation_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Generates overdue alerts and productivity insights with LLM reasoning and factual fallback."""
    intent = state.get("intent", Intent.GET_RECOMMENDATIONS.value)
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

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
        stats_res = await get_task_stats.ainvoke({"user_id": user_id})
        workload_res = await get_team_workload.ainvoke({})

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

