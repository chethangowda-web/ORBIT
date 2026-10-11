"""Conversation-state safety: follow-ups, confirmations and clarifications across turns.

Each test replays a multi-turn conversation through /chat/query (the real compiled graph with its
checkpointer), because the defects only appear when state carries over from one turn to the next.
"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agents.memory_agent import extract_task_id_from_text
from db.models import Task, User
from services.llm import fallback_intent_classifier  # noqa: F401  (ensures the offline classifier is importable)


async def say(client: AsyncClient, headers: dict, message: str, thread: str, **extra) -> dict:
    res = await client.post(
        "/api/chat/query", json={"message": message, "thread_id": thread, **extra}, headers=headers
    )
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def add_task(db: AsyncSession, creator: User, title: str, assignee: User | None = None, **kw) -> Task:
    task = Task(
        title=title,
        priority=kw.get("priority", "MEDIUM"),
        status=kw.get("status", "TODO"),
        created_by_id=creator.id,
        assignee_id=assignee.id if assignee else None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


# --- stale task id must not hijack later requests ------------------------------------------


async def test_old_task_reference_does_not_decide_a_later_ambiguous_request(
    client, db_session, seed_manager_user, manager_auth_headers
):
    a = await add_task(db_session, seed_manager_user, "Quarterly report draft")
    b = await add_task(db_session, seed_manager_user, "Quarterly report review")
    await say(client, manager_auth_headers, f"show details of task {a.id}", "stale-ref")

    reply = await say(client, manager_auth_headers, "complete the report task", "stale-ref")

    for task in (a, b):
        await db_session.refresh(task)
        assert task.status != "DONE", "an ambiguous request must not complete anything"
    assert "multiple" in reply["response"].lower() or "which" in reply["response"].lower()


async def test_follow_up_with_a_pronoun_still_works(client, db_session, seed_manager_user, manager_auth_headers):
    task = await add_task(db_session, seed_manager_user, "Prepare onboarding deck", priority="LOW")
    await say(client, manager_auth_headers, f"show details of task {task.id}", "pronoun")
    await say(client, manager_auth_headers, "make it high priority", "pronoun")
    await db_session.refresh(task)
    assert task.priority == "HIGH"


# --- cancel must only affect the cancel turn -----------------------------------------------


async def test_thread_works_normally_after_a_cancelled_delete(
    client, db_session, seed_manager_user, manager_auth_headers
):
    alpha = await add_task(db_session, seed_manager_user, "Alpha launch plan")
    await say(client, manager_auth_headers, "delete the alpha launch plan", "cancel-then-work")
    cancelled = await say(client, manager_auth_headers, "cancel", "cancel-then-work")
    assert "cancelled" in cancelled["response"].lower()

    later = await say(client, manager_auth_headers, "show my tasks", "cancel-then-work")
    assert "cancelled" not in later["response"].lower()
    assert later["metadata"]["intent"] == "GET_MY_TASKS"
    await db_session.refresh(alpha)
    assert alpha.deleted_at is None


# --- a confirmation only answers the question that was just asked --------------------------


async def test_a_later_yes_cannot_fire_an_old_delete_confirmation(
    client, db_session, seed_manager_user, manager_auth_headers
):
    alpha = await add_task(db_session, seed_manager_user, "Alpha launch plan")
    first = await say(client, manager_auth_headers, "delete the alpha launch plan", "stale-confirm")
    assert first["needs_confirmation"] is True

    await say(client, manager_auth_headers, "show my tasks", "stale-confirm")
    await say(client, manager_auth_headers, "yes", "stale-confirm")

    await db_session.refresh(alpha)
    assert alpha.deleted_at is None, "'yes' to a different conversation must not delete the task"


async def test_confirming_straight_after_the_question_still_works(
    client, db_session, seed_manager_user, manager_auth_headers
):
    alpha = await add_task(db_session, seed_manager_user, "Alpha launch plan")
    await say(client, manager_auth_headers, "delete the alpha launch plan", "confirm-now")
    done = await say(client, manager_auth_headers, "yes", "confirm-now")
    assert "deleted" in done["response"].lower()
    await db_session.refresh(alpha)
    assert alpha.deleted_at is not None


async def test_an_expired_confirmation_is_refused():
    from agents.review_agent import review_agent_node

    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    state = {
        "user_id": "u1",
        "thread_id": "t1",
        "confirmed": True,
        "pending_confirmation": {
            "action": "DELETE_TASK",
            "task_id": "00000000-0000-0000-0000-000000000001",
            "task_title": "Old",
            "user_id": "u1",
            "thread_id": "t1",
            "status": "PENDING",
            "created_at": old,
        },
    }
    result = await review_agent_node(state)
    assert "expired" in result["response"].lower()
    assert "delete_task" not in result["tool_calls_made"]


# --- task id extraction ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["make the task deadline tomorrow", "complete the task called report", "this task is edit-only", "Task force meeting"],
)
def test_ordinary_words_are_not_mistaken_for_task_ids(text):
    assert extract_task_id_from_text(text) is None


def test_real_task_ids_are_still_found():
    uid = "123e4567-e89b-12d3-a456-426614174000"
    assert extract_task_id_from_text(f"Created Task #{uid}: *Deploy*") == uid
    assert extract_task_id_from_text(f"details of {uid}") == uid


# --- no guessing --------------------------------------------------------------------------


async def test_update_without_a_clear_target_asks_instead_of_touching_the_only_task(
    client, db_session, seed_manager_user, seed_test_user, user_auth_headers
):
    only = await add_task(db_session, seed_manager_user, "Unrelated errand", assignee=seed_test_user, priority="LOW")
    reply = await say(client, user_auth_headers, "make it high priority", "no-guess")
    await db_session.refresh(only)
    assert only.priority == "LOW"
    assert "which task" in reply["response"].lower()


async def test_delete_with_several_matches_asks_which_one(
    client, db_session, seed_manager_user, manager_auth_headers
):
    a = await add_task(db_session, seed_manager_user, "Weekly report draft")
    b = await add_task(db_session, seed_manager_user, "Weekly report review")
    reply = await say(client, manager_auth_headers, "delete the weekly report task", "delete-ambiguous")
    assert reply["needs_confirmation"] is False
    assert "multiple" in reply["response"].lower() or "which" in reply["response"].lower()
    for task in (a, b):
        await db_session.refresh(task)
        assert task.deleted_at is None


async def test_mark_as_done_after_creating_a_task_completes_that_task(
    client, db_session, seed_test_user, user_auth_headers
):
    """The natural follow-up: no task is named, so it means the one just discussed."""
    created = await say(client, user_auth_headers, "create a task to send the invoice", "mark-done")
    assert "created" in created["response"].lower()
    done = await say(client, user_auth_headers, "mark as done", "mark-done")
    assert "completed" in done["response"].lower()


async def test_a_message_that_names_another_task_never_reuses_the_previous_one(
    client, db_session, seed_manager_user, manager_auth_headers
):
    a = await add_task(db_session, seed_manager_user, "Update the website copy")
    b = await add_task(db_session, seed_manager_user, "Send the invoice to Acme")
    await say(client, manager_auth_headers, f"show details of task {a.id}", "names-other")
    await say(client, manager_auth_headers, "mark the invoice task as done", "names-other")
    for task in (a, b):
        await db_session.refresh(task)
    assert a.status != "DONE"
    assert b.status == "DONE"


async def test_delete_never_inherits_the_previous_task_without_a_reference(
    client, db_session, seed_manager_user, manager_auth_headers
):
    a = await add_task(db_session, seed_manager_user, "Alpha launch plan")
    await say(client, manager_auth_headers, f"show details of task {a.id}", "delete-no-ref")
    reply = await say(client, manager_auth_headers, "delete", "delete-no-ref")
    assert reply["needs_confirmation"] is False
    await db_session.refresh(a)
    assert a.deleted_at is None
