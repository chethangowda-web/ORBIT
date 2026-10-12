"""Planner Agent: Synthesizes intelligent daily action plans based on deadlines and priority."""

import json
from typing import Any
from agents.prompts import PLANNER_PROMPT
from agents.state import AgentState
from db.base import local_today
from services.llm import call_llm
from services.week_plan import build_week_plan, format_week_plan
from tools.format_tools import friendly
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
    """Formats prioritized tasks into an actionable daily briefing (deterministic fallback)."""
    if not ranked_items:
        return "☀️ *Good day!* You have no pending tasks right now. Great job staying on top of everything!"

    lines = ["📋 *Your plan for today*", "Here is the order I suggest:\n"]
    for idx, (task, reason) in enumerate(ranked_items[:5], 1):
        title = task.get("title", "Untitled")
        priority = str(task.get("priority", "MEDIUM")).split(".")[-1]
        due = task.get("due_date") or "no due date"
        lines.append(f"*{idx}. {title}* ({friendly(priority)} priority)")
        lines.append(f"   • *Why:* {reason}")
        lines.append(f"   • *Due:* {due}\n")

    lines.append("💡 Start with the first one and work down the list.")
    return "\n".join(lines)


async def planner_agent_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node: Generates daily task plan for user with LLM synthesis and factual fallback."""
    user_id = state.get("user_id", "")
    tools_used: list[str] = list(state.get("tool_calls_made", []))

    if state.get("intent") == "PLAN_WEEK":
        # Scheduling is an algorithm, not a prompt: instant, explainable, and it needs no AI request.
        tools_used.append("get_user_tasks")
        mine = await get_user_tasks.ainvoke({"user_id": user_id, "limit": 200})
        tasks = mine.get("data", []) if mine.get("success") else []
        return {
            "response": format_week_plan(build_week_plan(tasks, local_today())),
            "response_type": "text",
            "card_data": None,
            "tool_calls_made": tools_used,
        }

    tools_used.extend(["get_tasks_due_today", "get_overdue_tasks", "get_user_tasks"])
    today_res = await get_tasks_due_today.ainvoke({"user_id": user_id})
    overdue_res = await get_overdue_tasks.ainvoke({"user_id": user_id})
    all_res = await get_user_tasks.ainvoke({"user_id": user_id})

    today_ids = {t["id"] for t in today_res.get("data", [])}
    overdue_ids = {t["id"] for t in overdue_res.get("data", [])}
    all_tasks = all_res.get("data", [])

    if not all_tasks:
        return {
            "response": "☀️ *Good day!* You have no pending tasks right now. Great job staying on top of everything!",
            "response_type": "text",
            "card_data": None,
            "tool_calls_made": tools_used,
        }

    scored_tasks: list[tuple[dict[str, Any], str, int]] = []
    for t in all_tasks:
        tid = t.get("id")
        is_over = tid in overdue_ids
        is_tod = tid in today_ids
        score = _rank_priority_score(t, is_over, is_tod)

        reason_parts = []
        if is_over:
            reason_parts.append("Already late")
        if is_tod:
            reason_parts.append("Due today")
        if t.get("priority") in ("HIGH", "CRITICAL"):
            reason_parts.append(f"{friendly(t.get('priority'))} priority")
        if t.get("status") == "IN_PROGRESS":
            reason_parts.append("Already in progress")

        reason = ", ".join(reason_parts) if reason_parts else "Next in line"
        scored_tasks.append((t, reason, score))

    scored_tasks.sort(key=lambda x: x[2], reverse=True)
    ranked = [(item[0], item[1]) for item in scored_tasks]

    # Attempt LLM synthesis with grounded task facts
    task_facts = [
        {
            "id": t.get("id"),
            "title": t.get("title"),
            "priority": str(t.get("priority", "MEDIUM")).split(".")[-1],
            "status": str(t.get("status", "TODO")).split(".")[-1],
            "due_date": t.get("due_date"),
            "is_overdue": t.get("id") in overdue_ids,
            "is_due_today": t.get("id") in today_ids,
            "preliminary_reason": reason,
        }
        for t, reason, _ in scored_tasks[:10]
    ]

    messages = [
        {"role": "system", "content": PLANNER_PROMPT},
        {
            "role": "user",
            "content": f"Here is the user's authentic active task data from the database:\n{json.dumps(task_facts, indent=2, default=str)}\n\nGenerate an intelligent, motivating daily action plan explaining the best order to tackle these tasks today.",
        },
    ]

    llm_plan = await call_llm(messages=messages, temperature=0.2)
    response_text = llm_plan.strip() if (llm_plan and isinstance(llm_plan, str) and len(llm_plan.strip()) > 20) else _format_plan_response(ranked)

    return {
        "response": response_text,
        "response_type": "text",
        "card_data": None,
        "tool_calls_made": tools_used,
    }

