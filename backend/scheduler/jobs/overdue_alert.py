"""Overdue Task Alert Job: Identifies overdue tasks and dispatches proactive warnings."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.base import local_midnight_utc, local_today, utc_now
from db.models import NotificationLog, Task, User
from crud.users import get_opted_out_user_ids
from metrics import record_notification
from services.notifications import deliver_with_retry
from tools.base import get_tool_session

logger = logging.getLogger(__name__)

PRIORITY_ICONS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "⚪",
}


async def _has_already_received_overdue_alert(session: AsyncSession, user_id: Any) -> bool:
    """Checks if a user has already received an overdue alert today (UTC)."""
    today_start = local_midnight_utc()
    query = select(NotificationLog).where(
        NotificationLog.user_id == user_id,
        NotificationLog.type == "overdue_alert",
        NotificationLog.sent_at >= today_start,
        NotificationLog.status == "sent",
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


def _format_overdue_message(user_name: str, tasks: List[Task]) -> str:
    """Formats overdue notification text with priority indicators."""
    lines = [
        f"🚨 *Overdue Tasks Alert for {user_name}*",
        f"You have {len(tasks)} overdue item(s) that require prompt attention:\n",
    ]
    for idx, task in enumerate(tasks, start=1):
        icon = PRIORITY_ICONS.get(task.priority, "⚪")
        due_str = task.due_date.isoformat() if task.due_date else "Unknown"
        lines.append(f"{idx}. {icon} *{task.title}* (Due: {due_str}, Priority: {task.priority})")

    lines.append(
        "\n💡 *Action items:* Please update task status in ORBIT or request a deadline extension."
    )
    return "\n".join(lines)


async def _dispatch_user_overdue_alert(
    session: AsyncSession,
    user: User,
    tasks: List[Task],
) -> str:
    """Dispatches the overdue alert, logs the real outcome, and returns its status."""
    msg = _format_overdue_message(user.display_name, tasks)
    delivery_status, error_msg = await deliver_with_retry(user, msg)
    record_notification("overdue_alert", delivery_status)
    session.add(
        NotificationLog(
            user_id=user.id,
            type="overdue_alert",
            message=msg,
            google_space_id=user.google_space_id or user.google_id,
            status=delivery_status,
            error_msg=error_msg,
            sent_at=utc_now(),
        )
    )
    await session.commit()
    return delivery_status


async def run_overdue_alerts(
    session: Optional[AsyncSession] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Finds all overdue tasks and sends warning alerts grouped by assignee."""
    summary: Dict[str, Any] = {
        "tasks_flagged": 0,
        "users_evaluated": 0,
        "sent": 0,
        "skipped": 0,
        "failed": 0,
    }

    async with get_tool_session(session) as s:
        today = local_today()
        stmt = (
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.status.not_in(["DONE", "CANCELLED"]),
                Task.due_date.is_not(None),
                Task.due_date < today,
            )
            .options(selectinload(Task.assignee))
        )
        result = await s.execute(stmt)
        overdue_tasks = result.scalars().all()
        summary["tasks_flagged"] = len(overdue_tasks)

        if not overdue_tasks:
            return summary

        # Group by assignee
        user_map: Dict[Any, List[Task]] = {}
        for task in overdue_tasks:
            if task.assignee and task.assignee.is_active:
                user_map.setdefault(task.assignee, []).append(task)

        summary["users_evaluated"] = len(user_map)
        opted_out = await get_opted_out_user_ids(s, "overdue_alert")

        for user, tasks in user_map.items():
            if user.id in opted_out:
                summary["skipped"] += 1
                continue
            if not force and await _has_already_received_overdue_alert(s, user.id):
                summary["skipped"] += 1
                continue

            try:
                outcome = await _dispatch_user_overdue_alert(s, user, tasks)
                summary[outcome] += 1
            except Exception as err:
                logger.error("Failed to dispatch overdue alert for %s: %s", user.id, err)
                summary["failed"] += 1

    return summary
