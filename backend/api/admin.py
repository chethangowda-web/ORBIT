"""ORBIT Admin & Diagnostic Endpoints: Manual scheduler triggers and system status."""

import math
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import timedelta
from pathlib import Path

from sqlalchemy import func, select

from config import settings
from crud.notifications import list_notification_logs
from db.base import utc_now
from db.models import AgentExecutionTrace, ChatEventLedger, NotificationLog, User
from services.email import email_enabled
from services.llm import llm_breaker
from db.session import get_db
from dependencies import require_role
from schemas.common import PaginationMeta, api_response
from scheduler.jobs.daily_briefing import run_daily_briefing
from scheduler.jobs.follow_ups import run_due_soon_reminders, run_manager_escalations, run_stale_nudges
from scheduler.jobs.overdue_alert import run_overdue_alerts
from scheduler.jobs.weekly_summary import run_weekly_summary
from scheduler.scheduler import get_scheduler_status

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/trigger-briefing", status_code=status.HTTP_200_OK)
async def trigger_daily_briefing(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually executes the morning briefing job for active users."""
    summary = await run_daily_briefing(force=force)
    return api_response(
        data=summary,
        meta={"action": "trigger_daily_briefing", "force": force, "triggered_by": str(current_user.id)},
    )


@router.post("/trigger-due-soon", status_code=status.HTTP_200_OK)
async def trigger_due_soon(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually sends the due-tomorrow reminders."""
    summary = await run_due_soon_reminders(force=force)
    return api_response(data=summary, meta={"action": "trigger_due_soon", "force": force, "triggered_by": str(current_user.id)})


@router.post("/trigger-stale-nudges", status_code=status.HTTP_200_OK)
async def trigger_stale_nudges(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually sends the check-ins about tasks that went quiet."""
    summary = await run_stale_nudges(force=force)
    return api_response(data=summary, meta={"action": "trigger_stale_nudges", "force": force, "triggered_by": str(current_user.id)})


@router.post("/trigger-escalations", status_code=status.HTTP_200_OK)
async def trigger_escalations(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually sends the late-work summary to managers."""
    summary = await run_manager_escalations(force=force)
    return api_response(data=summary, meta={"action": "trigger_escalations", "force": force, "triggered_by": str(current_user.id)})


@router.post("/trigger-overdue-alerts", status_code=status.HTTP_200_OK)
async def trigger_overdue_alerts(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually triggers proactive overdue task notifications."""
    summary = await run_overdue_alerts(force=force)
    return api_response(
        data=summary,
        meta={"action": "trigger_overdue_alerts", "force": force, "triggered_by": str(current_user.id)},
    )


@router.post("/trigger-weekly-summary", status_code=status.HTTP_200_OK)
async def trigger_weekly_summary(
    force: bool = Query(True, description="Bypass duplicate check if True"),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Manually triggers the weekly team productivity summary."""
    summary = await run_weekly_summary(force=force)
    return api_response(
        data=summary,
        meta={"action": "trigger_weekly_summary", "force": force, "triggered_by": str(current_user.id)},
    )


@router.get("/scheduler/status", status_code=status.HTTP_200_OK)
async def get_status(
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Returns current autonomous scheduler operational state and scheduled jobs."""
    info = get_scheduler_status()
    return api_response(data=info)


@router.get("/notifications", status_code=status.HTTP_200_OK)
async def list_notifications(
    delivery_status: Optional[str] = Query(None, alias="status", pattern="^(sent|failed|skipped)$"),
    type: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Delivery log for proactive and task-event notifications (managers and admins)."""
    items, total = await list_notification_logs(
        db, status=delivery_status, type_=type, page=page, page_size=page_size
    )
    meta = PaginationMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
    return api_response(data=items, meta=meta)


async def _delivery_counts(db: AsyncSession, email: bool) -> Dict[str, int]:
    """Notification outcomes in the last 24 hours (sent, failed, skipped) for Chat or for email."""
    since = utc_now() - timedelta(hours=24)
    is_email = NotificationLog.type.like("email:%")
    rows = await db.execute(
        select(NotificationLog.status, func.count())
        .where(NotificationLog.sent_at >= since, is_email if email else ~is_email)
        .group_by(NotificationLog.status)
    )
    counts = {"sent": 0, "failed": 0, "skipped": 0}
    for status_value, total in rows.all():
        counts[status_value] = counts.get(status_value, 0) + total
    return counts


def _has_chat_credentials() -> bool:
    inline = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    return inline.startswith("{") or bool(settings.GOOGLE_SERVICE_ACCOUNT_FILE and Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).exists())


@router.get("/integrations", status_code=status.HTTP_200_OK)
async def integrations_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin", "manager")),
) -> Dict[str, Any]:
    """Is each integration connected, and is it actually being used? Counts and booleans only: no
    secrets, addresses or message content."""
    since = utc_now() - timedelta(hours=24)

    events_24h = (await db.execute(select(func.count()).select_from(ChatEventLedger).where(ChatEventLedger.created_at >= since))).scalar_one()
    last_event = (await db.execute(select(func.max(ChatEventLedger.created_at)))).scalar_one()
    linked = (await db.execute(select(func.count()).select_from(User).where(User.google_id.is_not(None)))).scalar_one()
    dm_ready = (await db.execute(select(func.count()).select_from(User).where(User.google_space_id.is_not(None)))).scalar_one()

    classifier_rows = await db.execute(
        select(AgentExecutionTrace.classifier, func.count())
        .where(AgentExecutionTrace.created_at >= since)
        .group_by(AgentExecutionTrace.classifier)
    )
    classified = {(name or "unknown"): total for name, total in classifier_rows.all()}

    return api_response(
        data={
            "google_chat": {
                "verification_enabled": settings.GOOGLE_CHAT_VERIFY_AUTH,
                "audience_configured": bool(settings.GOOGLE_CHAT_AUDIENCE),
                "service_account_configured": _has_chat_credentials(),
                "events_24h": events_24h,
                "last_event_at": last_event.isoformat() if last_event else None,
                "linked_users": linked,
                "dm_ready_users": dm_ready,
                "deliveries_24h": await _delivery_counts(db, email=False),
            },
            "email": {
                "enabled": email_enabled(),
                "deliveries_24h": await _delivery_counts(db, email=True),
            },
            "llm": {
                "configured": bool(getattr(settings, "GOOGLE_GEMINI_API_KEY", "") or getattr(settings, "OPENAI_API_KEY", "")),
                "model": settings.DEFAULT_LLM_MODEL,
                "circuit_open": llm_breaker.opened_at is not None,
                "classified_24h": classified,
            },
        }
    )
