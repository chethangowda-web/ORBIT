"""ORBIT acts on its own: due-tomorrow reminders, check-ins on quiet tasks, late-work summaries."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import local_today, utc_now
from db.models import NotificationLog, Task, TaskComment, User, UserPreference
from scheduler.jobs.follow_ups import run_due_soon_reminders, run_manager_escalations, run_stale_nudges


@pytest.fixture(autouse=True)
def mock_chat_delivery():
    with patch("services.notifications.send_dm", new_callable=AsyncMock, return_value=True) as dm, patch(
        "services.notifications.send_text_message", new_callable=AsyncMock, return_value=True
    ):
        yield dm


async def link(db: AsyncSession, user: User) -> User:
    user.google_space_id = "spaces/DM-" + str(user.id)[:6]
    await db.commit()
    return user


async def task(db: AsyncSession, creator: User, title: str, assignee: User | None, **fields) -> Task:
    row = Task(title=title, priority=fields.pop("priority", "MEDIUM"), status=fields.pop("status", "TODO"),
               created_by_id=creator.id, assignee_id=assignee.id if assignee else None, **fields)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def logs(db: AsyncSession, type_: str) -> list[NotificationLog]:
    return list((await db.execute(select(NotificationLog).where(NotificationLog.type == type_))).scalars().all())


# --- due tomorrow --------------------------------------------------------------------------------


async def test_assignees_are_reminded_about_tasks_due_tomorrow(db_session, seed_test_user, mock_chat_delivery):
    await link(db_session, seed_test_user)
    await task(db_session, seed_test_user, "Send the contract", seed_test_user, due_date=local_today() + timedelta(days=1), priority="HIGH")
    await task(db_session, seed_test_user, "Due next week", seed_test_user, due_date=local_today() + timedelta(days=7))
    await task(db_session, seed_test_user, "Already done", seed_test_user, due_date=local_today() + timedelta(days=1), status="DONE")

    summary = await run_due_soon_reminders(session=db_session)

    assert summary["sent"] == 1
    sent = await logs(db_session, "due_soon_reminder")
    assert len(sent) == 1 and sent[0].status == "sent"
    assert "Send the contract" in sent[0].message
    assert "Due next week" not in sent[0].message and "Already done" not in sent[0].message
    assert "HIGH" not in sent[0].message, "priorities are written in plain words"
    assert "High priority" in sent[0].message


async def test_due_tomorrow_reminder_is_sent_once_a_day_and_respects_opt_out(db_session, seed_test_user):
    await link(db_session, seed_test_user)
    await task(db_session, seed_test_user, "Send the contract", seed_test_user, due_date=local_today() + timedelta(days=1))

    assert (await run_due_soon_reminders(session=db_session))["sent"] == 1
    again = await run_due_soon_reminders(session=db_session)
    assert again["sent"] == 0 and again["skipped"] == 1

    forced = await run_due_soon_reminders(session=db_session, force=True)
    assert forced["sent"] == 1

    db_session.add(UserPreference(user_id=seed_test_user.id, key="due_soon_reminder", value="off"))
    await db_session.commit()
    opted_out = await run_due_soon_reminders(session=db_session, force=True)
    assert opted_out["sent"] == 0 and opted_out["skipped"] == 1


async def test_a_person_without_chat_is_recorded_as_not_sent_not_as_sent(db_session, seed_test_user):
    await task(db_session, seed_test_user, "Send the contract", seed_test_user, due_date=local_today() + timedelta(days=1))
    summary = await run_due_soon_reminders(session=db_session)
    assert summary["sent"] == 0 and summary["skipped"] == 1
    assert (await logs(db_session, "due_soon_reminder"))[0].status == "skipped"


# --- tasks that went quiet -----------------------------------------------------------------------


async def make_quiet(db: AsyncSession, row: Task, days: int) -> None:
    await db.execute(update(Task).where(Task.id == row.id).values(updated_at=utc_now() - timedelta(days=days)))
    await db.commit()


async def test_in_progress_tasks_that_went_quiet_get_a_check_in(db_session, seed_test_user):
    await link(db_session, seed_test_user)
    quiet = await task(db_session, seed_test_user, "Migrate the old reports", seed_test_user, status="IN_PROGRESS")
    fresh = await task(db_session, seed_test_user, "Fresh work", seed_test_user, status="IN_PROGRESS")
    todo = await task(db_session, seed_test_user, "Not started", seed_test_user, status="TODO")
    for row in (quiet, todo):
        await make_quiet(db_session, row, 5)

    summary = await run_stale_nudges(session=db_session)

    assert summary["sent"] == 1
    message = (await logs(db_session, "stale_nudge"))[0].message
    assert "Migrate the old reports" in message
    assert "Fresh work" not in message and "Not started" not in message


async def test_a_task_people_are_commenting_on_is_not_quiet(db_session, seed_test_user):
    await link(db_session, seed_test_user)
    row = await task(db_session, seed_test_user, "Discussed a lot", seed_test_user, status="IN_PROGRESS")
    await make_quiet(db_session, row, 6)
    db_session.add(TaskComment(task_id=row.id, author_id=seed_test_user.id, body="Waiting on the vendor, almost there"))
    await db_session.commit()

    assert (await run_stale_nudges(session=db_session))["tasks"] == 0


async def test_check_ins_do_not_nag_every_day(db_session, seed_test_user):
    await link(db_session, seed_test_user)
    quiet = await task(db_session, seed_test_user, "Migrate the old reports", seed_test_user, status="IN_PROGRESS")
    await make_quiet(db_session, quiet, 6)

    assert (await run_stale_nudges(session=db_session))["sent"] == 1
    second = await run_stale_nudges(session=db_session)
    assert second["sent"] == 0 and second["skipped"] == 1, "one check-in every few days, not every day"


# --- late-work summary for managers --------------------------------------------------------------


async def test_managers_get_one_summary_of_work_that_is_several_days_late(
    db_session, seed_test_user, seed_manager_user
):
    await link(db_session, seed_manager_user)
    await link(db_session, seed_test_user)
    long_late = await task(db_session, seed_manager_user, "Renew the licence", seed_test_user, due_date=local_today() - timedelta(days=5), priority="CRITICAL")
    await task(db_session, seed_manager_user, "Only a day late", seed_test_user, due_date=local_today() - timedelta(days=1))
    await task(db_session, seed_manager_user, "Finished late", seed_test_user, due_date=local_today() - timedelta(days=9), status="DONE")

    summary = await run_manager_escalations(session=db_session)

    assert summary["sent"] == 1  # only the manager; the employee does not get a team summary
    row = (await logs(db_session, "manager_escalation"))[0]
    assert row.user_id == seed_manager_user.id
    assert "Renew the licence" in row.message and seed_test_user.display_name in row.message
    assert "5 days late" in row.message
    assert "Only a day late" not in row.message and "Finished late" not in row.message
    assert "CRITICAL" not in row.message
    assert long_late.title in row.message


async def test_no_summary_is_sent_when_nothing_is_badly_late(db_session, seed_manager_user):
    await link(db_session, seed_manager_user)
    summary = await run_manager_escalations(session=db_session)
    assert summary["sent"] == 0 and (await logs(db_session, "manager_escalation")) == []


# --- admin triggers --------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["trigger-due-soon", "trigger-stale-nudges", "trigger-escalations"])
async def test_managers_can_send_follow_ups_now_and_employees_cannot(client, manager_auth_headers, user_auth_headers, path):
    assert (await client.post(f"/api/admin/{path}", headers=user_auth_headers)).status_code == 403
    res = await client.post(f"/api/admin/{path}", headers=manager_auth_headers)
    assert res.status_code == 200
    assert set(res.json()["data"]) >= {"people", "tasks", "sent", "skipped", "failed"}
