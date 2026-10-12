"""'Undo that': reverse the last run of chat changes from the audit trail."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from agents.intents import Intent
from db.base import utc_now
from db.models import Task, TaskAuditLog
from services.llm import fallback_intent_classifier


@pytest.mark.parametrize("text", ["undo", "Undo that", "please undo it", "revert the last change", "roll back", "take that back", "undo that please!"])
def test_a_bare_undo_is_recognised(text):
    assert fallback_intent_classifier(text).intent == Intent.UNDO_LAST


@pytest.mark.parametrize("text", ["undo the deadline on the report task", "who undid the release task?", "move my tasks to Friday"])
def test_undo_inside_a_longer_request_is_not_an_undo(text):
    assert fallback_intent_classifier(text).intent != Intent.UNDO_LAST


async def ask(client, headers, text, thread="undo"):
    res = await client.post("/api/chat/query", json={"message": text, "thread_id": thread}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def audit(db, task, user, action, changes, *, seconds_ago=5, source="chat"):
    db.add(TaskAuditLog(task_id=task.id, user_id=user.id, action=action, changes=changes, source=source, created_at=utc_now() - timedelta(seconds=seconds_ago)))
    await db.commit()


async def make_task(db, owner, **fields):
    task = Task(title=fields.pop("title", "Report"), created_by_id=owner.id, assignee_id=owner.id, **fields)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def test_nothing_to_undo(client, seed_test_user, user_auth_headers):
    data = await ask(client, user_auth_headers, "undo")
    assert "nothing recent to undo" in data["response"]


async def test_undoing_a_status_change_restores_the_old_status(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, status="DONE", priority="HIGH")
    await audit(db_session, task, seed_test_user, "COMPLETED", {"status": {"old": "IN_PROGRESS", "new": "DONE"}})

    data = await ask(client, user_auth_headers, "undo that")
    assert "Put *Report* back as it was" in data["response"]
    await db_session.refresh(task)
    assert task.status == "IN_PROGRESS" and task.completed_at is None


async def test_undoing_a_creation_removes_the_task_and_a_second_undo_says_so(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, title="Just made")
    await audit(db_session, task, seed_test_user, "CREATED", {"title": {"new": "Just made"}})

    first = await ask(client, user_auth_headers, "undo")
    assert "Removed *Just made*" in first["response"]
    await db_session.refresh(task)
    assert task.deleted_at is not None

    second = await ask(client, user_auth_headers, "undo")
    assert "already been undone" in second["response"]


async def test_undoing_a_delete_brings_the_task_back(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, title="Oops")
    task.deleted_at = utc_now()
    await db_session.commit()
    await audit(db_session, task, seed_test_user, "DELETED", {"deleted_at": {"new": "now"}})

    data = await ask(client, user_auth_headers, "undo")
    assert "Brought back *Oops*" in data["response"]
    await db_session.refresh(task)
    assert task.deleted_at is None


async def test_a_run_of_several_changes_is_undone_together_newest_first(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, priority="CRITICAL", status="IN_PROGRESS")
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "LOW", "new": "HIGH"}}, seconds_ago=8)
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "HIGH", "new": "CRITICAL"}}, seconds_ago=6)
    await audit(db_session, task, seed_test_user, "STATUS_CHANGED", {"status": {"old": "TODO", "new": "IN_PROGRESS"}}, seconds_ago=5)

    await ask(client, user_auth_headers, "undo")
    await db_session.refresh(task)
    assert (task.priority, task.status) == ("LOW", "TODO")


async def test_only_the_last_run_is_undone_not_older_work(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, priority="HIGH")
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "LOW", "new": "MEDIUM"}}, seconds_ago=300)
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "MEDIUM", "new": "HIGH"}}, seconds_ago=5)

    await ask(client, user_auth_headers, "undo")
    await db_session.refresh(task)
    assert task.priority == "MEDIUM"


async def test_a_later_edit_by_someone_else_is_never_overwritten(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, priority="CRITICAL")  # changed again after ORBIT's change
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "LOW", "new": "HIGH"}})

    data = await ask(client, user_auth_headers, "undo")
    assert "was changed again since" in data["response"]
    await db_session.refresh(task)
    assert task.priority == "CRITICAL"


async def test_changes_older_than_half_an_hour_and_dashboard_edits_are_not_undone(client, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user, priority="HIGH")
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "LOW", "new": "HIGH"}}, seconds_ago=3600)
    await audit(db_session, task, seed_test_user, "UPDATED", {"priority": {"old": "LOW", "new": "HIGH"}}, source="api")

    assert "nothing recent to undo" in (await ask(client, user_auth_headers, "undo"))["response"]
    await db_session.refresh(task)
    assert task.priority == "HIGH"


async def test_you_can_only_undo_your_own_changes(client, db_session, seed_test_user, seed_manager_user, user_auth_headers):
    task = await make_task(db_session, seed_manager_user, priority="HIGH")
    await audit(db_session, task, seed_manager_user, "UPDATED", {"priority": {"old": "LOW", "new": "HIGH"}})

    assert "nothing recent to undo" in (await ask(client, user_auth_headers, "undo"))["response"]
    await db_session.refresh(task)
    assert task.priority == "HIGH"


async def test_undo_is_answered_without_the_ai(monkeypatch):
    from agents import supervisor

    async def boom(*a, **k):
        raise AssertionError("the AI must not be asked")

    monkeypatch.setattr(supervisor, "llm_available", lambda: True)
    monkeypatch.setattr(supervisor, "call_llm", boom)
    result, source = await supervisor.classify_intent_with_source("undo that")
    assert result.intent == Intent.UNDO_LAST and source == "quick"


async def test_end_to_end_create_a_task_in_chat_then_undo_it(client, db_session, seed_test_user, user_auth_headers):
    created = await ask(client, user_auth_headers, "Create a task Prepare the offsite agenda")
    assert "Prepare the offsite agenda" in created["response"]
    task = (await db_session.execute(select(Task).where(Task.title.ilike("%offsite agenda%")))).scalars().first()
    assert task is not None and task.deleted_at is None

    undone = await ask(client, user_auth_headers, "undo that")
    assert "Removed" in undone["response"]
    await db_session.refresh(task)
    assert task.deleted_at is not None
