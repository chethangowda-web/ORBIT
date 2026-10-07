"""ORBIT Admin & Diagnostic Endpoints: Manual scheduler triggers and system status."""

from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, status

from db.models import User
from dependencies import require_role
from schemas.common import api_response
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
