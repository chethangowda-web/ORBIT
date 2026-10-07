"""Daily Morning Briefing Job: Proactively synthesizes and dispatches daily action plans."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import utc_now
from db.models import NotificationLog, User
from db.session import async_session_factory
from services.google_chat import send_dm, send_text_message
from tools.base import get_tool_session
from tools.task_tools import get_overdue_tasks, get_tasks_due_today, get_user_tasks
from agents.planner_agent import _format_plan_response, _rank_priority_score

logger = logging.getLogger(__name__)


async def _has_already_received_briefing(session: AsyncSession, user_id: Any) -> bool:
    """Checks if user has already received a daily briefing today (UTC)."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = select(NotificationLog).where(
        NotificationLog.user_id == user_id,
        NotificationLog.type == "daily_briefing",
        NotificationLog.sent_at >= today_start,
        NotificationLog.status == "sent",
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


async def _generate_user_briefing_text(user_id_str: str) -> str:
    """Gathers user tasks and generates formatted daily plan."""
    today_res = await get_tasks_due_today.ainvoke({"user_id": user_id_str})
    overdue_res = await get_overdue_tasks.ainvoke({"user_id": user_id_str})
    all_res = await get_user_tasks.ainvoke({"user_id": user_id_str})

    today_ids = {t["id"] for t in today_res.get("data", [])}
    overdue_ids = {t["id"] for t in overdue_res.get("data", [])}
    all_tasks = all_res.get("data", [])

    scored_tasks = []
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

        reason = " | ".join(reason_parts) if reason_parts else "Standard queue item"
        scored_tasks.append((t, reason, score))

    scored_tasks.sort(key=lambda x: x[2], reverse=True)
    ranked = [(item[0], item[1]) for item in scored_tasks]
    return _format_plan_response(ranked)


async def run_daily_briefing(
    session: Optional[AsyncSession] = None,
    force: bool = False,
) -> dict[str, Any]:
    """Executes daily morning briefing workflow across all active users."""
    summary: dict[str, Any] = {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}

    async with get_tool_session(session) as s:
        result = await s.execute(select(User).where(User.is_active.is_(True)))
        users = result.scalars().all()
        summary["processed"] = len(users)

        for user in users:
            # Duplicate prevention check
            if not force and await _has_already_received_briefing(s, user.id):
                summary["skipped"] += 1
                continue

            try:
                user_id_str = str(user.id)
                plan_text = await _generate_user_briefing_text(user_id_str)
                full_message = f"🌅 *Good Morning, {user.display_name}!*\n\n{plan_text}"

                # Send via DM or space
                delivered = False
                if user.google_id:
                    delivered = await send_dm(user.google_id, full_message)
                elif user.google_space_id:
                    delivered = await send_text_message(user.google_space_id, full_message)
                else:
                    delivered = True  # Simulated delivery when no chat handles configured

                log_entry = NotificationLog(
                    user_id=user.id,
                    type="daily_briefing",
                    message=full_message,
                    google_space_id=user.google_space_id or user.google_id,
                    status="sent" if delivered else "failed",
                    sent_at=utc_now(),
                )
                s.add(log_entry)
                await s.commit()

                if delivered:
                    summary["sent"] += 1
                else:
                    summary["failed"] += 1

            except Exception as err:
                logger.error("Failed to generate briefing for user %s: %s", user.id, err)
                summary["failed"] += 1

    return summary
