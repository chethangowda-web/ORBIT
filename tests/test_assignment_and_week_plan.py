"""Smart assignment ("who should take this?") and week planning ("plan my week")."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agents.intents import Intent
from db.base import local_today
from db.models import Task, User
from services.assignment import rank_loads, score_of
from services.llm import fallback_intent_classifier
from services.week_plan import build_week_plan, format_week_plan, working_days

MONDAY = date(2026, 10, 12)  # a Monday


# --- who should take this ---------------------------------------------------------------------------------


def load(name: str, open_tasks: int, overdue: int = 0, high: int = 0, role: str = "employee"):
    return {"user_id": name, "name": name, "role": role, "open_tasks": open_tasks, "overdue_tasks": overdue, "high_priority_tasks": high}


def test_the_least_busy_person_ranks_first_and_late_work_counts_extra():
    ranked = rank_loads([load("Dev", 3), load("Asha", 1), load("Rahul", 1, overdue=2), load("Meera", 0)])
    assert [c.name for c in ranked] == ["Meera", "Asha", "Dev", "Rahul"]
    assert score_of(open_tasks=1, overdue=2, high=0) > score_of(open_tasks=3, overdue=0, high=0) - 1


def test_ties_are_broken_by_fewer_late_tasks_then_name():
    ranked = rank_loads([load("Zed", 2), load("Amy", 2), load("Bob", 2, overdue=1)])
    assert [c.name for c in ranked] == ["Amy", "Zed", "Bob"]


def test_the_reason_is_a_plain_sentence():
    best, second, third = rank_loads([load("A", 0), load("B", 1), load("C", 4, overdue=2)])
    assert best.reason == "no open tasks"
    assert second.reason == "1 open task, none late"
    assert third.reason == "4 open tasks, 2 late"


def test_admins_are_not_suggested_as_workers():
    assert [c.name for c in rank_loads([load("Root", 0, role="admin"), load("Asha", 5)])] == ["Asha"]


async def team(db: AsyncSession, manager: User) -> dict[str, User]:
    people = {}
    for name in ("Asha", "Dev", "Meera"):
        user = User(email=f"{name.lower()}@orbit.dev", display_name=name, role="employee", is_active=True)
        db.add(user)
        people[name] = user
    gone = User(email="gone@orbit.dev", display_name="Gone", role="employee", is_active=False)
    db.add(gone)
    await db.commit()
    for user in people.values():
        await db.refresh(user)
    today = local_today()
    rows = [
        Task(title="A1", priority="MEDIUM", status="TODO", created_by_id=manager.id, assignee_id=people["Asha"].id),
        Task(title="A2", priority="MEDIUM", status="TODO", created_by_id=manager.id, assignee_id=people["Asha"].id),
        Task(title="D1", priority="HIGH", status="TODO", created_by_id=manager.id, assignee_id=people["Dev"].id, due_date=today - timedelta(days=2)),
        Task(title="M done", priority="MEDIUM", status="DONE", created_by_id=manager.id, assignee_id=people["Meera"].id),
        Task(title="G1", priority="MEDIUM", status="TODO", created_by_id=manager.id, assignee_id=gone.id),
    ]
    db.add_all(rows)
    await db.commit()
    return people


async def test_the_api_suggests_who_has_room_and_only_to_managers(client, db_session, seed_manager_user, manager_auth_headers, user_auth_headers):
    await team(db_session, seed_manager_user)
    assert (await client.get("/api/planning/suggest-assignee", headers=user_auth_headers)).status_code == 403

    res = await client.get("/api/planning/suggest-assignee", headers=manager_auth_headers)
    assert res.status_code == 200
    items = res.json()["data"]
    names = [i["display_name"] for i in items]
    assert names[0] == "Meera", "finished work does not count, so she has the most room"
    assert "Gone" not in names, "inactive people are never suggested"
    assert items[0]["reason"] == "no open tasks" and items[0]["user_id"]


async def ask(client, headers, text, thread="assign") -> dict:
    res = await client.post("/api/chat/query", json={"message": text, "thread_id": thread}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.mark.parametrize(
    "text",
    [
        "who should take the API testing task?",
        "who is free right now",
        "who's the least busy",
        "who has capacity for a new project",
        "suggest someone for this",
    ],
)
def test_the_rules_recognise_requests_for_a_suggestion(text):
    assert fallback_intent_classifier(text).intent == Intent.SUGGEST_ASSIGNEE


def test_overload_questions_still_mean_workload_advice():
    assert fallback_intent_classifier("who is overloaded?").intent == Intent.GET_RECOMMENDATIONS


async def test_chat_suggests_the_best_person_without_any_AI(client, db_session, seed_manager_user, manager_auth_headers):
    await team(db_session, seed_manager_user)
    data = await ask(client, manager_auth_headers, "who should take the API testing task?")
    assert data["metadata"]["intent"] == "SUGGEST_ASSIGNEE"
    assert "Meera" in data["response"] and "no open tasks" in data["response"]
    assert "Gone" not in data["response"]
    assert data["metadata"]["steps"][-1]["node"] == "recommendation_agent"


async def test_employees_are_told_politely_that_they_cannot_hand_out_work(client, user_auth_headers, seed_test_user):
    data = await ask(client, user_auth_headers, "who should take this?", thread="assign-emp")
    assert "managers" in data["response"].lower() and "Meera" not in data["response"]


# --- planning a week --------------------------------------------------------------------------------------------


def task(title, priority="MEDIUM", due=None, status="TODO", id=None):
    return {"id": id or title, "title": title, "priority": priority, "status": status, "due_date": due}


def test_a_week_is_five_working_days_and_a_weekend_starts_on_monday():
    assert working_days(MONDAY) == [MONDAY + timedelta(days=i) for i in range(5)]
    saturday = MONDAY - timedelta(days=2)
    assert working_days(saturday)[0] == MONDAY
    assert working_days(MONDAY + timedelta(days=3))[:2] == [MONDAY + timedelta(days=3), MONDAY + timedelta(days=4)]
    assert working_days(MONDAY + timedelta(days=3))[2].weekday() == 0, "Friday is followed by Monday, not Saturday"


def test_late_work_comes_first_then_what_is_due_soonest():
    plan = build_week_plan(
        [
            task("Due Thursday", due=MONDAY + timedelta(days=3)),
            task("Late", due=MONDAY - timedelta(days=2)),
            task("Due Tuesday", due=MONDAY + timedelta(days=1)),
        ],
        today=MONDAY,
    )
    monday = [t.title for t in plan.days[0].tasks]
    assert monday[0] == "Late"
    assert plan.late_count == 1
    placed = {t.title: day.date for day in plan.days for t in day.tasks}
    assert placed["Due Tuesday"] <= MONDAY + timedelta(days=1)
    assert placed["Due Thursday"] <= MONDAY + timedelta(days=3)


def test_work_is_spread_across_the_week_not_piled_on_monday():
    plan = build_week_plan([task(f"T{i}", priority="HIGH") for i in range(6)], today=MONDAY, per_day=4)
    sizes = [len(d.tasks) for d in plan.days]
    assert sum(sizes) == 6 and max(sizes) <= 2, sizes
    assert plan.later == [] and plan.at_risk == []


def test_a_day_never_holds_more_than_the_daily_limit():
    plan = build_week_plan([task(f"T{i}") for i in range(30)], today=MONDAY, per_day=4)
    assert all(len(d.tasks) <= 4 for d in plan.days)
    assert len(plan.later) == 10


def test_a_task_goes_on_a_light_day_before_its_deadline_not_on_the_busiest_one():
    jobs = [task("Due Monday", due=MONDAY), task("Due Wednesday", due=MONDAY + timedelta(days=2)), task("Due Friday", due=MONDAY + timedelta(days=4))]
    plan = build_week_plan(jobs, today=MONDAY)
    placed = {t.title: d.date for d in plan.days for t in d.tasks}
    assert placed["Due Monday"] == MONDAY
    assert placed["Due Wednesday"] > MONDAY, "Monday already has work, so Wednesday's task goes to a lighter day"
    assert placed["Due Wednesday"] <= MONDAY + timedelta(days=2) and placed["Due Friday"] <= MONDAY + timedelta(days=4)


def test_a_deadline_that_cannot_be_met_is_flagged_not_hidden():
    jobs = [task(f"Due Monday {i}", due=MONDAY) for i in range(6)]
    plan = build_week_plan(jobs, today=MONDAY, per_day=4)
    flagged = {t.title for t in plan.at_risk}
    assert len(flagged) == 2, "the two that do not fit today are shown as tight, still on Monday"
    assert sum(len(d.tasks) for d in plan.days) == 6


def test_important_undated_work_beats_unimportant_undated_work_and_overflow_goes_to_later():
    jobs = [task(f"Low {i}", priority="LOW") for i in range(10)] + [task("Critical", priority="CRITICAL")]
    plan = build_week_plan(jobs, today=MONDAY, per_day=2)  # room for 10 of the 11
    assert plan.days[0].tasks[0].title == "Critical"
    assert len(plan.later) == 1 and plan.later[0].priority == "LOW"


def test_work_due_after_the_week_fills_gaps_but_never_displaces_this_weeks_deadlines():
    far = task("Next month", due=MONDAY + timedelta(days=30), priority="CRITICAL")
    now = task("Due today", due=MONDAY, priority="LOW")
    plan = build_week_plan([far, now], today=MONDAY, per_day=1)
    assert plan.days[0].tasks[0].title == "Due today"


def test_the_text_is_plain_and_lists_days_in_order():
    plan = build_week_plan(
        [task("Send the contract", priority="HIGH", due=MONDAY - timedelta(days=1)), task("Plan offsite", due=MONDAY + timedelta(days=2))],
        today=MONDAY,
    )
    text = format_week_plan(plan)
    assert "Monday 12 Oct" in text and "Tuesday 13 Oct" in text and text.index("Monday") < text.index("Tuesday")
    assert "High priority" in text and "HIGH" not in text
    assert "1 day late" in text


def test_an_empty_week_says_so():
    assert "clear" in format_week_plan(build_week_plan([], today=MONDAY)).lower()


@pytest.mark.parametrize("text", ["plan my week", "Plan the week for me", "what does my week look like", "schedule my week", "weekly plan"])
def test_the_rules_recognise_week_planning(text):
    assert fallback_intent_classifier(text).intent == Intent.PLAN_WEEK


def test_planning_a_day_is_not_confused_with_planning_a_week():
    assert fallback_intent_classifier("plan my day").intent == Intent.PLAN_DAY


async def test_the_api_returns_my_week(client, db_session, seed_test_user, seed_manager_user, user_auth_headers):
    today = local_today()
    db_session.add_all(
        [
            Task(title="Mine, due soon", priority="HIGH", status="TODO", created_by_id=seed_manager_user.id, assignee_id=seed_test_user.id, due_date=today + timedelta(days=1)),
            Task(title="Someone else's", priority="HIGH", status="TODO", created_by_id=seed_manager_user.id, assignee_id=seed_manager_user.id),
        ]
    )
    await db_session.commit()
    res = await client.get("/api/planning/week", headers=user_auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    titles = [t["title"] for d in data["days"] for t in d["tasks"]]
    assert titles == ["Mine, due soon"]
    assert len(data["days"]) == 5 and {"date", "label", "tasks"} <= set(data["days"][0])


async def test_chat_plans_the_week_without_any_AI(client, db_session, seed_test_user, seed_manager_user, user_auth_headers):
    db_session.add(Task(title="Prepare the deck", priority="HIGH", status="TODO", created_by_id=seed_manager_user.id, assignee_id=seed_test_user.id, due_date=local_today() + timedelta(days=2)))
    await db_session.commit()
    data = await ask(client, user_auth_headers, "plan my week", thread="week")
    assert data["metadata"]["intent"] == "PLAN_WEEK"
    assert data["metadata"]["steps"][-1]["node"] == "planner_agent"
    assert "Prepare the deck" in data["response"] and "Your week" in data["response"]
    assert "HIGH" not in data["response"]
