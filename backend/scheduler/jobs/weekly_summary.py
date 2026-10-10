"""Weekly Productivity Summary Job: Generates and dispatches team-wide metrics."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.base import local_midnight_utc, local_today, utc_now
from db.models import NotificationLog, User
from services.google_chat import send_dm, send_text_message
from tools.analytics_tools import get_task_stats
from tools.base import get_tool_session

logger = logging.getLogger(__name__)


async def _has_already_received_weekly_summary(
    session: AsyncSession,
    user_id: Any,
) -> bool:
    """Checks if a user has already received a weekly summary within the last 5 days."""
    cutoff = local_midnight_utc()
    query = select(NotificationLog).where(
        NotificationLog.user_id == user_id,
        NotificationLog.type == "weekly_summary",
        NotificationLog.sent_at >= cutoff,
        NotificationLog.status == "sent",
    )
    result = await session.execute(query)
    return result.scalar_one_or_none() is not None


def _format_weekly_summary_text(stats: Dict[str, Any]) -> str:
    """Formats team stats into a structured weekly digest."""
    total = stats.get("total_tasks", 0)
    completed = stats.get("completed_tasks", 0)
    overdue = stats.get("overdue_tasks", 0)
    in_progress = stats.get("in_progress_tasks", 0)
    completion_rate = (completed / total * 100) if total > 0 else 0.0

    lines = [
        "📊 *ORBIT Weekly Team Productivity Summary*",
        f"• *Total Tasks:* {total}",
        f"• *Completed:* {completed} ({completion_rate:.1f}%)",
        f"• *In Progress:* {in_progress}",
        f"• *Overdue:* {overdue}",
        "\n🚀 Wishing everyone a productive and focused week ahead!",
    ]
    return "\n".join(lines)


async def run_weekly_summary(
    session: Optional[AsyncSession] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Generates and dispatches weekly summary to leadership and configured spaces."""
    summary: Dict[str, Any] = {
        "sent": 0,
        "skipped": 0,
        "failed": 0,
        "stats": {},
    }

    async with get_tool_session(session) as s:
        stats_res = await get_task_stats.ainvoke({})
        stats_data = stats_res.get("data", {})
        summary["stats"] = stats_data
        digest = _format_weekly_summary_text(stats_data)

        # Broadcast to primary team space if configured
        if settings.GOOGLE_CHAT_SPACE_ID:
            try:
                await send_text_message(settings.GOOGLE_CHAT_SPACE_ID, digest)
            except Exception as err:
                logger.warning("Failed to broadcast weekly summary to space: %s", err)

        # Send to managers and admins
        stmt = select(User).where(
            User.is_active.is_(True),
            User.role.in_(["admin", "manager"]),
        )
        result = await s.execute(stmt)
        recipients = result.scalars().all()

        for user in recipients:
            if not force and await _has_already_received_weekly_summary(s, user.id):
                summary["skipped"] += 1
                continue

            try:
                delivered = False
                if user.google_id:
                    delivered = await send_dm(user.google_id, digest)
                elif user.google_space_id:
                    delivered = await send_text_message(user.google_space_id, digest)
                else:
                    delivered = True

                log_entry = NotificationLog(
                    user_id=user.id,
                    type="weekly_summary",
                    message=digest,
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
                logger.error("Failed to send weekly summary to %s: %s", user.id, err)
                summary["failed"] += 1

    return summary
