"""Google Chat replies: plain dates, one-tap task buttons, suggested next messages."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from db.base import local_today
from db.models import Task
from services.wording import due_phrase
from tools.format_tools import QUICK_REPLIES, format_task_list_card, format_task_list_text, quick_reply_section, task_summary_line

TODAY = date(2026, 10, 12)  # a Monday


@pytest.mark.parametrize(
    "due,expected",
    [
        (None, "no due date"),
        (TODAY, "due today"),
        (TODAY + timedelta(days=1), "due tomorrow"),
        (TODAY + timedelta(days=4), "due Friday"),
        (TODAY + timedelta(days=9), "due 21 Oct"),
        (TODAY - timedelta(days=1), "1 day late"),
        (TODAY - timedelta(days=5), "5 days late"),
        ("2026-10-13", "due tomorrow"),
    ],
)
def test_dates_are_said_the_way_people_say_them(due, expected):
    assert due_phrase(due, TODAY) == expected


def test_lists_never_show_raw_dates_or_the_phrase_due_no_due_date():
    tasks = [{"id": "a", "title": "A", "priority": "HIGH", "status": "TODO", "due_date": local_today().isoformat()}, {"id": "b", "title": "B", "priority": "LOW", "status": "TODO"}]
    text = format_task_list_text(tasks)
    assert "due today" in text and "no due date" in text and "due no due date" not in text and "2026-" not in text
    label = format_task_list_card(tasks)["cardsV2"][0]["card"]["sections"][0]["widgets"][1]["decoratedText"]["bottomLabel"]
    assert "due no due date" not in label


def test_a_task_summary_is_one_short_line():
    line = task_summary_line({"priority": "HIGH", "due_date": local_today() + timedelta(days=1), "assignee": {"display_name": "Sarah"}})
    assert line == "High priority · due tomorrow · with Sarah"


def test_quick_replies_only_carry_allow_listed_text():
    section = quick_reply_section(["Show my tasks", "Delete everything"], "spaces/X")
    buttons = section["widgets"][0]["buttonList"]["buttons"]
    assert [b["text"] for b in buttons] == ["Show my tasks"], "text outside the list is dropped"
    assert all(t in QUICK_REPLIES for t in ("Show my tasks", "Plan my day", "Plan my week", "What is overdue?", "Undo that"))


def click(email, action, params, stamp="1"):
    return {
        "type": "CARD_CLICKED",
        "eventTime": f"2026-10-12T09:00:0{stamp}Z",
        "space": {"name": "spaces/DM9", "type": "DM"},
        "user": {"name": "users/4242", "displayName": "Tester", "email": email},
        "action": {"actionMethodName": action, "parameters": [{"key": k, "value": v} for k, v in params.items()]},
    }


def message(email, text, stamp="1"):
    return {
        "type": "MESSAGE",
        "eventTime": f"2026-10-12T09:00:0{stamp}Z",
        "space": {"name": "spaces/DM9", "type": "DM"},
        "user": {"name": "users/4242", "displayName": "Tester", "email": email},
        "message": {"name": f"spaces/DM9/messages/{stamp}{abs(hash(text)) % 10**6}", "text": text},
    }


async def mine(db, user, **fields):
    task = Task(title=fields.pop("title", "Brief the team"), created_by_id=user.id, assignee_id=user.id, **fields)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def test_start_button_moves_the_task_into_progress(client: AsyncClient, db_session, seed_test_user):
    task = await mine(db_session, seed_test_user)
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "start_task", {"task_id": str(task.id)}))).json()
    assert "Started" in reply["text"]
    await db_session.refresh(task)
    assert task.status == "IN_PROGRESS"


async def test_due_tomorrow_button_pushes_the_deadline(client: AsyncClient, db_session, seed_test_user):
    task = await mine(db_session, seed_test_user, due_date=local_today() - timedelta(days=3))
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "snooze_task", {"task_id": str(task.id)}))).json()
    assert "due tomorrow" in reply["text"]
    await db_session.refresh(task)
    assert task.due_date == local_today() + timedelta(days=1)


async def test_buttons_cannot_touch_someone_elses_task(client: AsyncClient, db_session, seed_test_user, seed_manager_user):
    foreign = await mine(db_session, seed_manager_user, title="Manager only")
    for action in ("start_task", "snooze_task"):
        reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, action, {"task_id": str(foreign.id)}, stamp="2" if action == "start_task" else "3"))).json()
        assert "Permission denied" in reply["text"] or "❌" in reply["text"]
    await db_session.refresh(foreign)
    assert foreign.status == "TODO" and foreign.due_date is None


async def test_quick_reply_button_runs_the_phrase_and_unknown_text_is_refused(client: AsyncClient, db_session, seed_test_user):
    await mine(db_session, seed_test_user, title="Visible task")
    ok = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "quick_reply", {"text": "Show my tasks"}))).json()
    assert "Visible task" in str(ok)

    refused = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "quick_reply", {"text": "Delete every task"}, stamp="2"))).json()
    assert "no longer available" in refused["text"]


async def test_replies_offer_next_steps_and_creating_a_task_shows_its_buttons(client: AsyncClient, db_session, seed_test_user):
    greeting = (await client.post("/api/chat/webhook", json=message(seed_test_user.email, "hi", "4"))).json()
    labels = [b["text"] for b in greeting["cardsV2"][0]["card"]["sections"][0]["widgets"][0]["buttonList"]["buttons"]]
    assert labels == ["Show my tasks", "Plan my day", "Plan my week"]

    created = (await client.post("/api/chat/webhook", json=message(seed_test_user.email, "Create a task Draft the launch email by friday", "5"))).json()
    assert "Added" in created["text"] and "due" in created["text"]
    buttons = [b["text"] for b in created["cardsV2"][0]["card"]["sections"][1]["widgets"][0]["buttonList"]["buttons"]]
    assert buttons == ["Done", "Start", "Due tomorrow", "Undo"]
    task = (await db_session.execute(select(Task).where(Task.title.ilike("%launch email%")))).scalars().first()
    assert task is not None


async def test_undo_button_reverses_the_last_chat_change(client: AsyncClient, db_session, seed_test_user):
    await client.post("/api/chat/webhook", json=message(seed_test_user.email, "Create a task Order team lunch", "6"))
    reply = (await client.post("/api/chat/webhook", json=click(seed_test_user.email, "undo_last", {}, stamp="7"))).json()
    assert "Removed" in reply["text"]
