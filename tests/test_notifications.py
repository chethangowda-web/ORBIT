"""Tests for outbound task-event notifications (Flow C: dashboard/chat -> Google Chat)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from crud import tasks as task_crud
from db.models import NotificationLog, User
from schemas.task import TaskCreate, TaskPriority, TaskUpdate


@pytest.mark.asyncio
async def test_assignment_to_other_user_sends_notification(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Assigning a task to someone else than the actor dispatches a delivered notification."""
    seed_test_user.google_id = "users/employee001"
    await db_session.commit()

    with patch("services.notifications.send_dm", new_callable=AsyncMock) as mock_send_dm:
        mock_send_dm.return_value = True
        task_in = TaskCreate(title="Deploy service", priority=TaskPriority.HIGH, assignee_id=seed_test_user.id)
        await task_crud.create_task(db_session, task_in, created_by_id=seed_manager_user.id, source="api")
        mock_send_dm.assert_awaited_once()

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "task_assigned",
        )
    )
    log = res.scalar_one_or_none()
    assert log is not None
    assert log.status == "sent"
    assert "Deploy service" in log.message


@pytest.mark.asyncio
async def test_self_assignment_sends_no_notification(
    db_session: AsyncSession, seed_test_user: User
):
    """A user assigning a task to themselves must not receive a self-notification."""
    with patch("services.notifications.send_dm", new_callable=AsyncMock) as mock_send_dm:
        task_in = TaskCreate(title="Write docs", priority=TaskPriority.LOW, assignee_id=seed_test_user.id)
        await task_crud.create_task(db_session, task_in, created_by_id=seed_test_user.id, source="api")
        mock_send_dm.assert_not_awaited()

    res = await db_session.execute(
        select(NotificationLog).where(NotificationLog.user_id == seed_test_user.id)
    )
    assert res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_assignment_without_chat_handle_is_marked_skipped(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Recipient with no linked Google Chat handle: never claim delivery, record 'skipped'."""
    task_in = TaskCreate(title="Audit logging", priority=TaskPriority.MEDIUM, assignee_id=seed_test_user.id)
    await task_crud.create_task(db_session, task_in, created_by_id=seed_manager_user.id, source="api")

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "task_assigned",
        )
    )
    log = res.scalar_one_or_none()
    assert log is not None
    assert log.status == "skipped"


@pytest.mark.asyncio
async def test_notification_delivery_failure_does_not_roll_back_task(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """A failed Chat API delivery must not undo the already-committed task mutation."""
    seed_test_user.google_id = "users/employee002"
    await db_session.commit()

    with patch("services.notifications.send_dm", new_callable=AsyncMock) as mock_send_dm:
        mock_send_dm.return_value = False
        task_in = TaskCreate(title="Fix prod incident", priority=TaskPriority.CRITICAL, assignee_id=seed_test_user.id)
        created = await task_crud.create_task(db_session, task_in, created_by_id=seed_manager_user.id, source="api")

    reloaded = await task_crud.get_task(db_session, created.id)
    assert reloaded is not None
    assert reloaded.title == "Fix prod incident"

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "task_assigned",
        )
    )
    log = res.scalar_one_or_none()
    assert log is not None
    assert log.status == "failed"


@pytest.mark.asyncio
async def test_completion_by_other_user_notifies_creator(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Completing a task created by someone else notifies the creator, not the completer."""
    seed_manager_user.google_id = "users/manager001"
    await db_session.commit()

    task_in = TaskCreate(title="Rotate credentials", priority=TaskPriority.HIGH, assignee_id=seed_test_user.id)
    created = await task_crud.create_task(db_session, task_in, created_by_id=seed_manager_user.id, source="api")

    with patch("services.notifications.send_dm", new_callable=AsyncMock) as mock_send_dm:
        mock_send_dm.return_value = True
        await task_crud.complete_task(db_session, created.id, user_id=seed_test_user.id, source="chat")
        mock_send_dm.assert_awaited_once()

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_manager_user.id,
            NotificationLog.type == "task_completed",
        )
    )
    log = res.scalar_one_or_none()
    assert log is not None
    assert log.status == "sent"


@pytest.mark.asyncio
async def test_reassignment_notifies_new_assignee(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Updating a task's assignee notifies the newly assigned user."""
    seed_test_user.google_id = "users/employee003"
    await db_session.commit()

    task_in = TaskCreate(title="Write release notes", priority=TaskPriority.LOW)
    created = await task_crud.create_task(db_session, task_in, created_by_id=seed_manager_user.id, source="api")

    with patch("services.notifications.send_dm", new_callable=AsyncMock) as mock_send_dm:
        mock_send_dm.return_value = True
        update = TaskUpdate(assignee_id=seed_test_user.id)
        await task_crud.update_task(db_session, created.id, update, user_id=seed_manager_user.id, source="api")
        mock_send_dm.assert_awaited_once()

    res = await db_session.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == seed_test_user.id,
            NotificationLog.type == "task_assigned",
        )
    )
    assert res.scalar_one_or_none() is not None
