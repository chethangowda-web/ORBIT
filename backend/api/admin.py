"""ORBIT Admin & Diagnostic Endpoints: Manual scheduler triggers and system status."""

import math
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from crud.notifications import list_notification_logs
from db.models import User
from db.session import get_db
from dependencies import require_role
from schemas.common import PaginationMeta, api_response
from scheduler.jobs.daily_briefing import run_daily_briefing
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
