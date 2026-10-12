"""Google Chat slash commands, task-list cards and the one-click Complete button."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from api.webhook import expand_slash_command
from db.models import Task, User
from tools.format_tools import MAX_CARD_TASKS, format_task_list_card


def event(email: str, text: str = "", **extra) -> dict:
    base = {
        "type": "MESSAGE",
        "eventTime": "2026-10-10T09:00:00Z",
        "space": {"name": "spaces/DM1", "type": "DM"},
        "user": {"name": f"users/{abs(hash(email)) % 10**8}", "displayName": "Tester", "email": email},
        "message": {"name": f"spaces/DM1/messages/{abs(hash(text + email)) % 10**9}", "text": text},
    }
    base["message"].update(extra)
    return base


def click(email: str, action: str, task_id: str, stamp: str = "1") -> dict:
    return {
        "type": "CARD_CLICKED",
        "eventTime": f"2026-10-10T09:00:0{stamp}Z",
        "space": {"name": "spaces/DM1", "type": "DM"},
        "user": {"name": f"users/{abs(hash(email)) % 10**8}", "displayName": "Tester", "email": email},
        "action": {"actionMethodName": action, "parameters": [{"key": "task_id", "value": task_id}]},
    }


async def add_task(db, owner: User, **fields) -> Task:
    task = Task(title=fields.pop("title", "Task"), created_by_id=owner.id, assignee_id=owner.id, **fields)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@pytest.mark.parametrize(
    "text,command_id,argument,expected",
    [
        ("/tasks", None, None, "Show my pending tasks"),
        ("/PLAN", None, None, "Plan my day"),
        ("/overdue", None, None, "What are my overdue tasks?"),
        ("/insights", None, None, "Give me workload recommendations"),
        ("/help", None, None, "help"),
        ("/new Fix the login bug", None, None, "Create a task Fix the login bug"),
        ("/new", None, None, "help"),
        ("anything", "2", None, "Show my pending tasks"),
        ("anything", "5", "Write docs", "Create a task Write docs"),
        ("/unknown thing", None, None, "/unknown thing"),
        ("show my tasks", None, None, "show my tasks"),
        ("what is 5/2", None, None, "what is 5/2"),
    ],
)
def test_expand_slash_command(text, command_id, argument, expected):
    assert expand_slash_command(text, command_id, argument) == expected


def test_task_list_card_has_done_button_per_open_task_only():
    tasks = [
        {"id": "a", "title": "Open one", "priority": "HIGH", "status": "TODO", "due_date": "2026-10-12"},
        {"id": "b", "title": "Finished", "priority": "LOW", "status": "DONE"},
    ]
    card = format_task_list_card(tasks, title="Your tasks")
    widgets = card["cardsV2"][0]["card"]["sections"][0]["widgets"]
    assert "button" in widgets[0]["decoratedText"]
    assert widgets[0]["decoratedText"]["button"]["onClick"]["action"]["parameters"] == [{"key": "task_id", "value": "a"}]
    assert "button" not in widgets[1]["decoratedText"]
    assert card["chat_text"] == "📋 *Your tasks* (2)"


def test_task_list_card_truncates_long_lists():
    tasks = [{"id": str(i), "title": f"T{i}", "status": "TODO", "priority": "LOW"} for i in range(MAX_CARD_TASKS + 5)]
    widgets = format_task_list_card(tasks)["cardsV2"][0]["card"]["sections"][0]["widgets"]
    assert len(widgets) == MAX_CARD_TASKS + 1
    assert "5 more" in widgets[-1]["textParagraph"]["text"]


async def test_slash_tasks_replies_with_interactive_card(client: AsyncClient, db_session, seed_test_user):
    await add_task(db_session, seed_test_user, title="Write the report")
    reply = (await client.post("/api/chat/webhook", json=event(seed_test_user.email, "/tasks"))).json()

    assert reply["text"].startswith("📋")
    assert "Write the report" not in reply["text"]  # the card carries the list
    widgets = reply["cardsV2"][0]["card"]["sections"][0]["widgets"]
    assert "Write the report" in widgets[0]["decoratedText"]["text"]
    assert "button" in widgets[0]["decoratedText"]


async def test_command_id_from_chat_console_is_honoured(client: AsyncClient, db_session, seed_test_user):
    await add_task(db_session, seed_test_user, title="Plan target")
    msg = event(seed_test_user.email, "Plan my day please", slashCommand={"commandId": "3"})
    reply = (await client.post("/api/chat/webhook", json=msg)).json()
    assert "Plan" in reply["text"] or "Action Plan" in reply["text"]


async def test_done_button_completes_the_task(client: AsyncClient, db_session, seed_test_user):
    task = await add_task(db_session, seed_test_user, title="Ship it")
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "complete_task", str(task.id)))).json()

    assert "Ship it" in reply["text"] and "completed" in reply["text"]
    await db_session.refresh(task)
    assert task.status == "DONE" and task.completed_at is not None


async def test_done_button_cannot_complete_someone_elses_task(client: AsyncClient, db_session, seed_test_user, seed_manager_user):
    foreign = await add_task(db_session, seed_manager_user, title="Manager only")
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "complete_task", str(foreign.id)))).json()

    assert "Permission denied" in reply["text"]
    await db_session.refresh(foreign)
    assert foreign.status == "TODO"


async def test_double_clicking_done_is_processed_once(client: AsyncClient, db_session, seed_test_user):
    task = await add_task(db_session, seed_test_user, title="Once only")
    payload = click(seed_test_user.email, "complete_task", str(task.id))
    first = (await client.post("/api/chat/webhook", json=payload)).json()
    second = (await client.post("/api/chat/webhook", json=payload)).json()

    assert first["text"] == second["text"]  # replayed from the ledger, not re-run
    from db.models import TaskAuditLog

    logs = (await db_session.execute(select(TaskAuditLog).where(TaskAuditLog.task_id == task.id, TaskAuditLog.action == "COMPLETED"))).scalars().all()
    assert len(logs) == 1


async def test_done_button_with_unknown_task_reports_cleanly(client: AsyncClient, seed_test_user):
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "complete_task", "00000000-0000-0000-0000-000000000000"))).json()
    assert reply["text"].startswith("❌")


async def test_users_sharing_a_space_do_not_share_conversation_state(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user
):
    """A manager's pending delete confirmation must not leak into an employee's turn."""
    await add_task(db_session, seed_test_user, title="Employee task")
    await add_task(db_session, seed_manager_user, title="Doomed task")

    room = {"name": "spaces/ROOM1", "type": "ROOM"}
    manager_msg = event(seed_manager_user.email, "Delete the Doomed task")
    manager_msg["space"] = room
    first = (await client.post("/api/chat/webhook", json=manager_msg)).json()
    assert "Please confirm" in first["text"]

    employee_msg = event(seed_test_user.email, "/tasks")
    employee_msg["space"] = room
    reply = (await client.post("/api/chat/webhook", json=employee_msg)).json()
    assert reply["text"].startswith("📋"), reply
    assert "Please confirm" not in reply["text"]


async def test_pronouns_never_resolve_to_another_users_task_in_a_shared_thread(
    client: AsyncClient, db_session, seed_manager_user, seed_admin_user
):
    """'make it high priority' must refer to MY last task, not a colleague's, in a shared room."""
    room = {"name": "spaces/ROOM2", "type": "ROOM"}

    created = event(seed_manager_user.email, "Create a task to Write the quarterly report")
    created["space"] = room
    first = (await client.post("/api/chat/webhook", json=created)).json()
    assert "Created" in first["text"]

    follow_up = event(seed_admin_user.email, "Make it high priority")
    follow_up["space"] = room
    reply = (await client.post("/api/chat/webhook", json=follow_up)).json()

    assert "Updated" not in reply["text"], reply
    assert "Which task" in reply["text"]
    task = (await db_session.execute(select(Task).where(Task.title.ilike("%quarterly%")))).scalars().one()
    assert task.priority != "HIGH"
