"""The chat/agent path must enforce the same access rules as the REST API."""

import pytest
from httpx import AsyncClient

from db.models import Task, User
from tools.task_tools import create_task, get_task_by_id, search_tasks
from tools.user_tools import get_team_workload
from tools.analytics_tools import get_task_stats


async def _add(db, creator, assignee=None, **fields) -> Task:
    task = Task(title=fields.pop("title", "T"), created_by_id=creator.id,
                assignee_id=assignee.id if assignee else None, **fields)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def _ask(client: AsyncClient, headers: dict, message: str, thread: str = "t") -> dict:
    response = await client.post(
        "/api/chat/query", json={"message": message, "thread_id": thread}, headers=headers
    )
    assert response.status_code == 200
    return response.json()["data"]


async def test_employee_search_only_sees_own_tasks(
    client, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    await _add(db_session, seed_manager_user, seed_manager_user, title="Confidential salary review")
    await _add(db_session, seed_test_user, seed_test_user, title="Salary spreadsheet cleanup")

    data = await _ask(client, user_auth_headers, "search for salary")
    assert "Salary spreadsheet cleanup" in data["response"]
    assert "Confidential salary review" not in data["response"]


async def test_search_tool_scopes_employee_but_not_manager(
    db_session, seed_test_user, seed_manager_user
):
    await _add(db_session, seed_manager_user, seed_manager_user, title="manager only budget")

    as_employee = await search_tasks.ainvoke({"query": "budget", "viewer_id": str(seed_test_user.id)})
    as_manager = await search_tasks.ainvoke({"query": "budget", "viewer_id": str(seed_manager_user.id)})
    assert as_employee["data"] == []
    assert len(as_manager["data"]) == 1


async def test_get_task_by_id_hides_foreign_tasks_from_employees(
    db_session, seed_test_user, seed_manager_user
):
    secret = await _add(db_session, seed_manager_user, seed_manager_user, title="secret")
    mine = await _add(db_session, seed_test_user, seed_test_user, title="mine")

    blocked = await get_task_by_id.ainvoke({"task_id": str(secret.id), "viewer_id": str(seed_test_user.id)})
    assert blocked["success"] is False and "not found" in blocked["error"]  # no existence leak
    allowed = await get_task_by_id.ainvoke({"task_id": str(mine.id), "viewer_id": str(seed_test_user.id)})
    assert allowed["success"] is True


async def test_team_workload_tool_refuses_employees(db_session, seed_test_user, seed_manager_user):
    denied = await get_team_workload.ainvoke({"viewer_id": str(seed_test_user.id)})
    assert denied["success"] is False
    ok = await get_team_workload.ainvoke({"viewer_id": str(seed_manager_user.id)})
    assert ok["success"] is True


async def test_recommendations_do_not_leak_team_data_to_employees(
    client, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    for i in range(5):
        await _add(db_session, seed_manager_user, seed_manager_user, title=f"mgr task {i}")
    data = await _ask(client, user_auth_headers, "give me workload recommendations")
    assert "Test Manager" not in data["response"]
    assert "Team Load Alert" not in data["response"]


async def test_stats_tool_scopes_employee(db_session, seed_test_user, seed_manager_user):
    await _add(db_session, seed_manager_user, seed_manager_user)
    await _add(db_session, seed_test_user, seed_test_user)
    employee = await get_task_stats.ainvoke({"viewer_id": str(seed_test_user.id)})
    manager = await get_task_stats.ainvoke({"viewer_id": str(seed_manager_user.id)})
    assert employee["data"]["total_tasks"] == 1
    assert manager["data"]["total_tasks"] == 2


async def test_unknown_calling_user_is_denied_not_allowed(db_session):
    import uuid

    ghost = str(uuid.uuid4())
    result = await create_task.ainvoke({"title": "x", "created_by_id": ghost})
    assert result["success"] is False and "Permission denied" in result["error"]


async def test_unknown_assignee_is_reported_not_silently_self_assigned(
    client, seed_test_user, user_auth_headers
):
    data = await _ask(client, user_auth_headers, "Create a task for Zorblax to deploy the frontend")
    assert "could not find" in data["response"].lower()


async def test_ambiguous_assignee_asks_which_person(
    client, db_session, seed_manager_user, manager_auth_headers
):
    db_session.add_all([
        User(email="joe.a@orbit.dev", display_name="Joe Alpha", role="employee", is_active=True),
        User(email="joe.b@orbit.dev", display_name="Joe Beta", role="employee", is_active=True),
    ])
    await db_session.commit()

    data = await _ask(client, manager_auth_headers, "Create a task for Joe to write the report")
    assert "more than one person" in data["response"].lower()
    assert "Joe Alpha" in data["response"] and "Joe Beta" in data["response"]


async def test_exact_name_beats_partial_matches(db_session, seed_manager_user):
    from tools.base import resolve_user_reference

    db_session.add_all([
        User(email="jo@orbit.dev", display_name="Jo", role="employee", is_active=True),
        User(email="joanna@orbit.dev", display_name="Joanna Reed", role="employee", is_active=True),
    ])
    await db_session.commit()

    user, problem = await resolve_user_reference(db_session, "Jo")
    assert problem is None and user.email == "jo@orbit.dev"


async def test_complete_without_target_asks_instead_of_guessing(
    client, db_session, seed_test_user, user_auth_headers
):
    task = await _add(db_session, seed_test_user, seed_test_user, title="Do not touch me")
    data = await _ask(client, user_auth_headers, "complete it")
    assert "which task" in data["response"].lower()
    await db_session.refresh(task)
    assert task.status == "TODO"


async def test_complete_with_ambiguous_title_asks_which_one(
    client, db_session, seed_test_user, user_auth_headers
):
    await _add(db_session, seed_test_user, seed_test_user, title="Deploy staging")
    await _add(db_session, seed_test_user, seed_test_user, title="Deploy production")
    data = await _ask(client, user_auth_headers, "mark the deploy task as completed")
    assert "several tasks match" in data["response"].lower()


async def test_employee_delete_request_does_not_reveal_task_titles(
    client, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    await _add(db_session, seed_manager_user, seed_manager_user, title="Layoff plan")
    data = await _ask(client, user_auth_headers, "delete the layoff plan task")
    assert "Layoff plan" not in data["response"]
    assert data["needs_confirmation"] is False


async def test_recommendation_completion_rate_is_a_percentage(
    client, db_session, seed_manager_user, manager_auth_headers
):
    await _add(db_session, seed_manager_user, seed_manager_user, status="DONE")
    await _add(db_session, seed_manager_user, seed_manager_user, status="TODO")
    data = await _ask(client, manager_auth_headers, "give me insights")
    assert "50%" in data["response"]
