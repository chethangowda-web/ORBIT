"""Unit & Integration Tests for ORBIT Autonomous Scheduler and Admin Triggers."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import local_today
from db.models import NotificationLog, Task, User, UserPreference
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


@pytest.fixture(autouse=True)
def mock_chat_delivery():
    """Jobs deliver through services.notifications; never hit Google Chat in tests."""
    with patch("services.notifications.send_text_message", new_callable=AsyncMock, return_value=True) as text,          patch("services.notifications.send_dm", new_callable=AsyncMock, return_value=True) as dm,          patch("scheduler.jobs.weekly_summary.send_text_message", new_callable=AsyncMock, return_value=True):
        yield {"text": text, "dm": dm}


async def link_chat(db: AsyncSession, user: User, space: str = "spaces/TESTDM") -> User:
    """Give a user a Google Chat DM space so deliveries can succeed."""
    user.google_space_id = space
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_daily_briefing_job(db_session: AsyncSession, seed_test_user: User):
    """Test morning briefing generation, delivery, and audit logging."""
    await link_chat(db_session, seed_test_user)
    today = local_today()
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
    await link_chat(db_session, seed_test_user)
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
    await link_chat(db_session, seed_test_user)
    overdue_date = local_today() - timedelta(days=3)
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
    await link_chat(db_session, seed_test_user)
    overdue_date = local_today() - timedelta(days=2)
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
    await link_chat(db_session, seed_manager_user)
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


class _FakeRedis:
    """Minimal async Redis double implementing SET NX EX semantics."""

    store: set[str] = set()

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store.add(key)
        return True

    async def aclose(self):
        return None


async def test_job_lock_runs_once_per_firing(monkeypatch):
    import scheduler.scheduler as sched_module

    _FakeRedis.store = set()
    monkeypatch.setattr(sched_module.aioredis, "from_url", lambda *a, **k: _FakeRedis())
    calls: list[int] = []

    async def job():
        calls.append(1)
        return "done"

    locked = sched_module.with_job_lock("unit_test_job", job)
    assert await locked() == "done"
    assert await locked() is None  # second worker is turned away
    assert calls == [1]


async def test_job_lock_falls_back_to_running_when_redis_down(monkeypatch):
    import scheduler.scheduler as sched_module

    def boom(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(sched_module.aioredis, "from_url", boom)
    calls: list[int] = []

    async def job():
        calls.append(1)
        return "ran"

    assert await sched_module.with_job_lock("unit_test_job", job)() == "ran"
    assert calls == [1]


async def test_users_without_chat_handle_are_skipped_not_sent(db_session, seed_test_user):
    """No handle means nothing was delivered, so the log must say skipped (never sent)."""
    summary = await run_daily_briefing(session=db_session, force=True)
    assert summary["sent"] == 0 and summary["skipped"] >= 1

    logs = (await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == seed_test_user.id)
    )).scalars().all()
    assert [log.status for log in logs] == ["skipped"]
    assert "no linked google chat" in logs[0].error_msg.lower()


async def test_failed_delivery_is_logged_as_failed(db_session, seed_test_user, mock_chat_delivery, monkeypatch):
    import services.notifications as notifications

    monkeypatch.setattr(notifications, "RETRY_BACKOFF_SECONDS", 0)
    await link_chat(db_session, seed_test_user)
    mock_chat_delivery["text"].return_value = False
    mock_chat_delivery["dm"].return_value = False

    summary = await run_daily_briefing(session=db_session, force=True)
    assert summary["failed"] >= 1 and summary["sent"] == 0
    log = (await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == seed_test_user.id)
    )).scalars().one()
    assert log.status == "failed" and log.error_msg


@pytest.mark.parametrize("key,job", [
    ("daily_briefing", run_daily_briefing),
    ("overdue_alert", run_overdue_alerts),
])
async def test_opted_out_users_receive_nothing_even_when_forced(db_session, seed_test_user, key, job):
    await link_chat(db_session, seed_test_user)
    db_session.add(Task(title="Late", status="TODO", priority="HIGH", assignee_id=seed_test_user.id,
                        created_by_id=seed_test_user.id, due_date=local_today() - timedelta(days=2)))
    db_session.add(UserPreference(user_id=seed_test_user.id, key=key, value="false"))
    await db_session.commit()

    summary = await job(session=db_session, force=True)
    assert summary["sent"] == 0
    logs = (await db_session.execute(select(NotificationLog))).scalars().all()
    assert logs == []


async def test_cancelled_overdue_tasks_do_not_trigger_alerts(db_session, seed_test_user):
    await link_chat(db_session, seed_test_user)
    db_session.add(Task(title="Dropped", status="CANCELLED", priority="HIGH", assignee_id=seed_test_user.id,
                        created_by_id=seed_test_user.id, due_date=local_today() - timedelta(days=5)))
    await db_session.commit()
    summary = await run_overdue_alerts(session=db_session, force=True)
    assert summary["tasks_flagged"] == 0 and summary["sent"] == 0


async def test_opt_in_preference_values_are_case_insensitive(db_session, seed_test_user):
    from crud.users import get_opted_out_user_ids

    db_session.add(UserPreference(user_id=seed_test_user.id, key="daily_briefing", value="FALSE"))
    await db_session.commit()
    assert seed_test_user.id in await get_opted_out_user_ids(db_session, "daily_briefing")
    assert await get_opted_out_user_ids(db_session, "overdue_alert") == set()
