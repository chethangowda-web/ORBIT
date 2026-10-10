"""Notification delivery log queries."""

from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NotificationLog, User


async def list_notification_logs(
    db: AsyncSession,
    status: Optional[str] = None,
    type_: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Dict[str, Any]], int]:
    """Newest-first delivery records with the recipient's name, plus the total count."""
    filters = []
    if status:
        filters.append(NotificationLog.status == status)
    if type_:
        filters.append(NotificationLog.type == type_)

    total = (
        await db.execute(select(func.count()).select_from(NotificationLog).where(*filters))
    ).scalar_one()

    stmt = (
        select(NotificationLog, User.display_name)
        .join(User, User.id == NotificationLog.user_id)
        .where(*filters)
        .order_by(NotificationLog.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    items = [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "user_name": name,
            "type": log.type,
            "status": log.status,
            "message": log.message,
            "error_msg": log.error_msg,
            "sent_at": log.sent_at.isoformat(),
        }
        for log, name in rows
    ]
    return items, total
