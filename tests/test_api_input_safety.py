"""Inputs that used to be accepted, saved, and then made the task list return 500 for everyone."""

import uuid

import pytest
from httpx import AsyncClient


async def create(client, headers, **body) -> dict:
    res = await client.post("/api/tasks", json={"title": "Seed task", **body}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["data"]


@pytest.mark.parametrize("title", ["   ", "\t\n", ""])
async def test_blank_titles_are_rejected_and_nothing_is_saved(client: AsyncClient, user_auth_headers, title):
    res = await client.post("/api/tasks", json={"title": title}, headers=user_auth_headers)
    assert res.status_code == 422
    listing = await client.get("/api/tasks", headers=user_auth_headers)
    assert listing.status_code == 200 and listing.json()["data"] == []


@pytest.mark.parametrize("field", ["title", "status", "priority", "tags"])
async def test_patching_required_fields_to_null_is_a_validation_error(client, user_auth_headers, field):
    task = await create(client, user_auth_headers)
    res = await client.patch(f"/api/tasks/{task['id']}", json={field: None}, headers=user_auth_headers)
    assert res.status_code == 422, "null must not reach the database"
    # The task is still readable, singly and in lists.
    assert (await client.get(f"/api/tasks/{task['id']}", headers=user_auth_headers)).status_code == 200
    assert (await client.get("/api/tasks", headers=user_auth_headers)).status_code == 200


async def test_a_blank_title_cannot_be_set_through_patch(client, user_auth_headers):
    task = await create(client, user_auth_headers)
    res = await client.patch(f"/api/tasks/{task['id']}", json={"title": "   "}, headers=user_auth_headers)
    assert res.status_code == 422


async def test_optional_fields_can_still_be_cleared(client, manager_auth_headers):
    task = await create(client, manager_auth_headers, description="d", due_date="2030-01-01")
    res = await client.patch(
        f"/api/tasks/{task['id']}", json={"description": None, "due_date": None, "assignee_id": None},
        headers=manager_auth_headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["description"] is None and data["due_date"] is None


async def test_assigning_to_a_user_that_does_not_exist_is_a_clean_error(client, manager_auth_headers):
    ghost = str(uuid.uuid4())
    create_res = await client.post(
        "/api/tasks", json={"title": "x", "assignee_id": ghost}, headers=manager_auth_headers
    )
    assert create_res.status_code in (404, 422)

    task = await create(client, manager_auth_headers)
    patch_res = await client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": ghost}, headers=manager_auth_headers)
    assert patch_res.status_code in (404, 422)
    still = await client.get(f"/api/tasks/{task['id']}", headers=manager_auth_headers)
    assert still.json()["data"]["assignee_id"] is None


async def test_bulk_assign_to_a_missing_user_reports_each_task_instead_of_failing_the_batch(
    client, manager_auth_headers
):
    one, two = await create(client, manager_auth_headers), await create(client, manager_auth_headers)
    res = await client.post(
        "/api/tasks/bulk",
        json={"task_ids": [one["id"], two["id"]], "action": "assign", "value": str(uuid.uuid4())},
        headers=manager_auth_headers,
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["succeeded"] == [] and len(body["failed"]) == 2


async def test_employee_cannot_unassign_or_reassign_but_may_keep_the_current_assignee(
    client, db_session, seed_test_user, user_auth_headers, seed_manager_user, manager_auth_headers
):
    """An employee who created a task that a manager owns can still edit it (the edit form sends the
    unchanged assignee back), but cannot take it away from the manager or hand it to someone else."""
    task = await create(client, manager_auth_headers, assignee_id=str(seed_manager_user.id))
    # make the employee a creator/owner so they can edit it
    from sqlalchemy import update
    from db.models import Task

    await db_session.execute(update(Task).where(Task.id == uuid.UUID(task["id"])).values(created_by_id=seed_test_user.id))
    await db_session.commit()

    keep = await client.patch(
        f"/api/tasks/{task['id']}",
        json={"title": "Renamed by creator", "assignee_id": str(seed_manager_user.id)},
        headers=user_auth_headers,
    )
    assert keep.status_code == 200, keep.text

    unassign = await client.patch(f"/api/tasks/{task['id']}", json={"assignee_id": None}, headers=user_auth_headers)
    assert unassign.status_code == 403
    other = await client.patch(
        f"/api/tasks/{task['id']}", json={"assignee_id": str(uuid.uuid4())}, headers=user_auth_headers
    )
    assert other.status_code in (403, 404, 422)
