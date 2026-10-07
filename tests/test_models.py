"""
Tests for Phase 1 Database Models & Relations
"""

import uuid
from datetime import date, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_password_hash
from db.models import NotificationLog, Task, TaskAuditLog, User, UserPreference


@pytest.mark.asyncio
async def test_create_user_and_task(db_session: AsyncSession):
    """Test creating user and task with foreign keys and relationships."""
    user = User(
        email="developer@orbit.dev",
        hashed_password=get_password_hash("pass"),
        display_name="Dev User",
        role="employee",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    task = Task(
        title="Setup Redis Cache",
        description="Configure Redis for rate limiting and LangGraph checkpointing.",
        priority="HIGH",
        status="TODO",
        due_date=date.today() + timedelta(days=2),
        created_by_id=user.id,
        assignee_id=user.id,
        tags=["redis", "infra"],
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    assert task.id is not None
    assert task.assignee.display_name == "Dev User"
    assert task.creator.email == "developer@orbit.dev"


@pytest.mark.asyncio
async def test_task_audit_log(db_session: AsyncSession):
    """Test inserting and linking task audit log."""
    user = User(
        email="author@orbit.dev",
        hashed_password=get_password_hash("pass"),
        display_name="Author",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    task = Task(
        title="Sample Task",
        created_by_id=user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    audit = TaskAuditLog(
        task_id=task.id,
        user_id=user.id,
        action="CREATED",
        changes={"status": {"new": "TODO"}},
        source="api",
    )
    db_session.add(audit)
    await db_session.commit()

    stmt = select(TaskAuditLog).where(TaskAuditLog.task_id == task.id)
    result = await db_session.execute(stmt)
    logs = result.scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "CREATED"
    assert logs[0].source == "api"


@pytest.mark.asyncio
async def test_user_preference_and_notifications(db_session: AsyncSession):
    """Test UserPreference and NotificationLog models."""
    user = User(
        email="prefuser@orbit.dev",
        hashed_password=get_password_hash("pass"),
        display_name="Pref User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    pref = UserPreference(
        user_id=user.id,
        key="daily_briefing",
        value="true",
    )
    notif = NotificationLog(
        user_id=user.id,
        type="daily_briefing",
        message="Good morning! You have 2 tasks due today.",
        status="sent",
    )
    db_session.add_all([pref, notif])
    await db_session.commit()

    stmt = select(UserPreference).where(UserPreference.user_id == user.id)
    res_pref = (await db_session.execute(stmt)).scalars().first()
    assert res_pref.key == "daily_briefing"

    stmt_notif = select(NotificationLog).where(NotificationLog.user_id == user.id)
    res_notif = (await db_session.execute(stmt_notif)).scalars().first()
    assert res_notif.type == "daily_briefing"
    assert res_notif.status == "sent"
