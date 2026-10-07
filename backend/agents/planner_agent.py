"""Planner Agent: Synthesizes intelligent daily action plans based on deadlines and priority."""

from typing import Any
from agents.state import AgentState
from tools.task_tools import (
    get_overdue_tasks,
    get_tasks_due_today,
    get_user_tasks,
)


def _rank_priority_score(task: dict[str, Any], is_overdue: bool, is_today: bool) -> int:
    """Computes ranking score for task prioritization."""
    score = 0
    if is_overdue:
        score += 100
    if is_today:
        score += 80

    p = (task.get("priority") or "MEDIUM").upper()
    p_weights = {"CRITICAL": 50, "HIGH": 30, "MEDIUM": 10, "LOW": 0}
    score += p_weights.get(p, 10)

    if task.get("status") == "IN_PROGRESS":
        score += 15
    return score


def _format_plan_response(ranked_items: list[tuple[dict[str, Any], str]]) -> str:
    """Formats prioritized tasks into an actionable daily briefing."""
    if not ranked_items:
        return "☀️ *Good day!* You have no pending tasks right now. Great job staying on top of everything!"

    lines = ["📋 *Your Daily Action Plan*", "Here is your recommended focus order for today:\n"]
    for idx, (task, reason) in enumerate(ranked_items[:5], 1):
        title = task.get("title", "Untitled")
        priority = task.get("priority", "MEDIUM")
        due = task.get("due_date", "No due date")
        lines.append(f"*{idx}. {title}* `[{priority}]`")
        lines.append(f"   • *Why:* {reason}")
        lines.append(f"   • *Due:* {due}\n")

    lines.append("💡 *Tip:* Tackle the highest urgency items first to unblock your team.")
    return "\n".join(lines)


async def planner_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Generates daily task plan for user."""
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    tools_used.extend(["get_tasks_due_today", "get_overdue_tasks", "get_user_tasks"])
    today_res = await get_tasks_due_today.ainvoke({"user_id": user_id})
    overdue_res = await get_overdue_tasks.ainvoke({"user_id": user_id})
    all_res = await get_user_tasks.ainvoke({"user_id": user_id})

    today_ids = {t["id"] for t in today_res.get("data", [])}
    overdue_ids = {t["id"] for t in overdue_res.get("data", [])}
    all_tasks = all_res.get("data", [])

    scored_tasks: list[tuple[dict[str, Any], str, int]] = []
    for t in all_tasks:
        tid = t.get("id")
        is_over = tid in overdue_ids
        is_tod = tid in today_ids
        score = _rank_priority_score(t, is_over, is_tod)

        reason_parts = []
        if is_over:
            reason_parts.append("Overdue — requires immediate resolution")
        if is_tod:
            reason_parts.append("Due today")
        if t.get("priority") in ("HIGH", "CRITICAL"):
            reason_parts.append(f"{t.get('priority')} priority impact")
        if t.get("status") == "IN_PROGRESS":
            reason_parts.append("Already in progress")

        reason = " | ".join(reason_parts) if reason_parts else "Standard pending queue item"
        scored_tasks.append((t, reason, score))

    scored_tasks.sort(key=lambda x: x[2], reverse=True)
    ranked = [(item[0], item[1]) for item in scored_tasks]

    response_text = _format_plan_response(ranked)
    return {
        "response": response_text,
        "response_type": "text",
        "card_data": None,
        "tool_calls_made": tools_used,
    }
