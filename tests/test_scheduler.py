"""Unit & Integration Tests for ORBIT Autonomous Scheduler and Admin Triggers."""

from datetime import date, timedelta
from typing import Any
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NotificationLog, Task, User
from scheduler.jobs.daily_briefing import run_daily_briefing
from scheduler.jobs.overdue_alert import run_overdue_alerts
from scheduler.jobs.weekly_summary import run_weekly_summary
from scheduler.scheduler import get_scheduler_status, register_default_jobs, scheduler


@pytest.mark.asyncio
async def test_scheduler_status_and_registration():
    """Verify scheduler registers cron jobs properly."""
    register_default_jobs(scheduler)
    status_info = get_scheduler_status()
    assert isinstance(status_info, dict)
    assert "running" in status_info
    assert "timezone" in status_info
    assert status_info["timezone"] == "Asia/Kolkata"


@pytest.mark.asyncio
async def test_daily_briefing_job(db_session: AsyncSession, seed_test_user: User):
    """Test morning briefing generation, delivery, and audit logging."""
    today = date.today()
    # Create sample task for user
    task = Task(
        title="Deploy microservice",
        description="Deploy frontend & backend",
        status="TODO",
        priority="HIGH",
        due_date=today,
        assignee_id=seed_test_user.id,
        created_by_id=seed_test_user.id,
    )
    db_session.add(task)
    await db_session.commit()

    summary = await run_daily_briefing(session=db_session, force=True)
    assert summary["processed"] >= 1
    assert summary["sent"] >= 1

    # Check notification log created
    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "daily_briefing",
        )
    )
    logs = res.scalars().all()
    assert len(logs) >= 1
    assert logs[0].status == "sent"
    assert "Deploy microservice" in logs[0].message


@pytest.mark.asyncio
async def test_daily_briefing_duplicate_prevention(
    db_session: AsyncSession, seed_test_user: User
):
    """Verify duplicate briefing is skipped on subsequent executions within the same day."""
    # First execution: sent
    summary_1 = await run_daily_briefing(session=db_session, force=False)
    assert summary_1["sent"] >= 1

    # Second execution without force: skipped
    summary_2 = await run_daily_briefing(session=db_session, force=False)
    assert summary_2["skipped"] >= 1

    # Third execution with force=True: bypassed
    summary_3 = await run_daily_briefing(session=db_session, force=True)
    assert summary_3["sent"] >= 1


@pytest.mark.asyncio
async def test_overdue_alerts_job(db_session: AsyncSession, seed_test_user: User):
    """Test overdue tasks detection and notification dispatch."""
    overdue_date = date.today() - timedelta(days=3)
    task = Task(
        title="Urgent DB Migration",
        description="Run migration script",
        status="IN_PROGRESS",
        priority="CRITICAL",
        due_date=overdue_date,
        assignee_id=seed_test_user.id,
        created_by_id=seed_test_user.id,
    )
    db_session.add(task)
    await db_session.commit()

    summary = await run_overdue_alerts(session=db_session, force=True)
    assert summary["tasks_flagged"] >= 1
    assert summary["sent"] >= 1

    # Check notification log
    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "overdue_alert",
        )
    )
    logs = res.scalars().all()
    assert len(logs) >= 1
    assert logs[0].status == "sent"
    assert "Urgent DB Migration" in logs[0].message


@pytest.mark.asyncio
async def test_overdue_alerts_duplicate_prevention(
    db_session: AsyncSession, seed_test_user: User
):
    """Test overdue alerts are skipped when already dispatched today."""
    overdue_date = date.today() - timedelta(days=2)
    task = Task(
        title="Patch Security Bug",
        status="TODO",
        priority="HIGH",
        due_date=overdue_date,
        assignee_id=seed_test_user.id,
        created_by_id=seed_test_user.id,
    )
    db_session.add(task)
    await db_session.commit()

    sum_1 = await run_overdue_alerts(session=db_session, force=False)
    assert sum_1["sent"] >= 1

    sum_2 = await run_overdue_alerts(session=db_session, force=False)
    assert sum_2["skipped"] >= 1


@pytest.mark.asyncio
async def test_weekly_summary_job(db_session: AsyncSession, seed_manager_user: User):
    """Test weekly productivity digest generation and delivery to management."""
    summary = await run_weekly_summary(session=db_session, force=True)
    assert summary["sent"] >= 1
    assert "stats" in summary

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_manager_user.id,
            NotificationLog.type == "weekly_summary",
        )
    )
    logs = res.scalars().all()
    assert len(logs) >= 1
    assert "Weekly Team Productivity" in logs[0].message


@pytest.mark.asyncio
async def test_admin_endpoints_authorization(
    client: AsyncClient,
    user_auth_headers: dict,
    manager_auth_headers: dict,
):
    """Test RBAC protection and execution of administrative scheduler endpoints."""
    # Employee cannot access admin triggers (403 Forbidden)
    res_forbidden = await client.post(
        "/api/admin/trigger-briefing", headers=user_auth_headers
    )
    assert res_forbidden.status_code == 403

    # Manager can access status
    res_status = await client.get(
        "/api/admin/scheduler/status", headers=manager_auth_headers
    )
    assert res_status.status_code == 200
    assert res_status.json()["data"]["timezone"] == "Asia/Kolkata"

    # Manager can trigger daily briefing
    res_briefing = await client.post(
        "/api/admin/trigger-briefing?force=true", headers=manager_auth_headers
    )
    assert res_briefing.status_code == 200
    assert res_briefing.json()["data"]["processed"] >= 1

    # Manager can trigger overdue alerts
    res_overdue = await client.post(
        "/api/admin/trigger-overdue-alerts?force=true", headers=manager_auth_headers
    )
    assert res_overdue.status_code == 200
    assert "tasks_flagged" in res_overdue.json()["data"]

    # Manager can trigger weekly summary
    res_weekly = await client.post(
        "/api/admin/trigger-weekly-summary?force=true", headers=manager_auth_headers
    )
    assert res_weekly.status_code == 200
    assert "stats" in res_weekly.json()["data"]
