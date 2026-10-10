"""Bulk task actions: per-task authorisation, partial failure, validation."""

import uuid

from httpx import AsyncClient

from db.models import Task, User


async def make(db, creator: User, assignee: User | None = None, **fields) -> Task:
    task = Task(title=fields.pop("title", "T"), created_by_id=creator.id, assignee_id=(assignee or creator).id, **fields)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def bulk(client: AsyncClient, headers: dict, ids, action: str, value: str | None = None):
    body = {"task_ids": [str(i) for i in ids], "action": action}
    if value is not None:
        body["value"] = value
    return await client.post("/api/tasks/bulk", json=body, headers=headers)


async def test_manager_completes_many_tasks(client: AsyncClient, db_session, seed_manager_user, manager_auth_headers):
    tasks = [await make(db_session, seed_manager_user, title=f"T{i}") for i in range(3)]
    res = (await bulk(client, manager_auth_headers, [t.id for t in tasks], "complete")).json()["data"]

    assert len(res["succeeded"]) == 3 and res["failed"] == []
    for t in tasks:
        await db_session.refresh(t)
        assert t.status == "DONE" and t.completed_at is not None


async def test_one_forbidden_task_does_not_block_the_rest(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    mine_a = await make(db_session, seed_test_user, title="mine a")
    mine_b = await make(db_session, seed_test_user, title="mine b")
    foreign = await make(db_session, seed_manager_user, title="not mine")

    # Capture ids first: the test client shares one session with the app, and the app's
    # per-task rollback expires objects held by the test (real requests have their own session).
    a_id, b_id, foreign_id = mine_a.id, mine_b.id, foreign.id
    res = (await bulk(client, user_auth_headers, [a_id, foreign_id, b_id], "complete")).json()["data"]
    assert set(res["succeeded"]) == {str(a_id), str(b_id)}
    assert [f["id"] for f in res["failed"]] == [str(foreign_id)]
    assert "permission" in res["failed"][0]["reason"].lower()

    await db_session.refresh(foreign)
    assert foreign.status == "TODO"


async def test_employees_cannot_bulk_delete(client: AsyncClient, db_session, seed_test_user, user_auth_headers):
    tasks = [await make(db_session, seed_test_user) for _ in range(2)]
    res = (await bulk(client, user_auth_headers, [t.id for t in tasks], "delete")).json()["data"]
    assert res["succeeded"] == [] and len(res["failed"]) == 2
    for t in tasks:
        await db_session.refresh(t)
        assert t.deleted_at is None


async def test_manager_bulk_delete_is_a_soft_delete(client: AsyncClient, db_session, seed_manager_user, manager_auth_headers):
    task = await make(db_session, seed_manager_user)
    res = (await bulk(client, manager_auth_headers, [task.id], "delete")).json()["data"]
    assert res["succeeded"] == [str(task.id)]
    await db_session.refresh(task)
    assert task.deleted_at is not None


async def test_bulk_status_and_priority(client: AsyncClient, db_session, seed_manager_user, manager_auth_headers):
    tasks = [await make(db_session, seed_manager_user) for _ in range(2)]
    ids = [t.id for t in tasks]
    await bulk(client, manager_auth_headers, ids, "set_status", "REVIEW")
    await bulk(client, manager_auth_headers, ids, "set_priority", "CRITICAL")
    for t in tasks:
        await db_session.refresh(t)
        assert (t.status, t.priority) == ("REVIEW", "CRITICAL")


async def test_invalid_values_are_rejected(client: AsyncClient, seed_manager_user, manager_auth_headers):
    ids = [uuid.uuid4()]
    assert (await bulk(client, manager_auth_headers, ids, "set_status", "NOPE")).status_code == 422
    assert (await bulk(client, manager_auth_headers, ids, "set_priority", "URGENT")).status_code == 422
    assert (await bulk(client, manager_auth_headers, ids, "assign", "not-a-uuid")).status_code == 422
    assert (await bulk(client, manager_auth_headers, ids, "explode")).status_code == 422


async def test_size_limits(client: AsyncClient, seed_manager_user, manager_auth_headers):
    assert (await bulk(client, manager_auth_headers, [], "complete")).status_code == 422
    assert (await bulk(client, manager_auth_headers, [uuid.uuid4() for _ in range(51)], "complete")).status_code == 422


async def test_assignment_rules(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers, manager_auth_headers
):
    task = await make(db_session, seed_test_user)

    # Employees can assign to themselves or unassign, not hand work to others.
    denied = (await bulk(client, user_auth_headers, [task.id], "assign", str(seed_manager_user.id))).json()["data"]
    assert denied["succeeded"] == [] and "cannot assign" in denied["failed"][0]["reason"].lower()
    ok_self = (await bulk(client, user_auth_headers, [task.id], "assign", str(seed_test_user.id))).json()["data"]
    assert ok_self["succeeded"] == [str(task.id)]
    unassigned = (await bulk(client, user_auth_headers, [task.id], "assign", "")).json()["data"]
    assert unassigned["succeeded"] == [str(task.id)]
    await db_session.refresh(task)
    assert task.assignee_id is None

    # Managers can assign to anyone.
    ok = (await bulk(client, manager_auth_headers, [task.id], "assign", str(seed_test_user.id))).json()["data"]
    assert ok["succeeded"] == [str(task.id)]
    await db_session.refresh(task)
    assert task.assignee_id == seed_test_user.id


async def test_duplicates_unknown_ids_and_cancelled_tasks(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    good = await make(db_session, seed_manager_user)
    cancelled = await make(db_session, seed_manager_user, status="CANCELLED")
    ghost = uuid.uuid4()

    res = (await bulk(client, manager_auth_headers, [good.id, good.id, cancelled.id, ghost], "complete")).json()["data"]
    assert res["succeeded"] == [str(good.id)]  # the duplicate is processed once
    reasons = {f["id"]: f["reason"] for f in res["failed"]}
    assert "cancelled" in reasons[str(cancelled.id)].lower()
    assert "not found" in reasons[str(ghost)].lower()


async def test_each_change_is_audited(client: AsyncClient, db_session, seed_manager_user, manager_auth_headers):
    task = await make(db_session, seed_manager_user)
    await bulk(client, manager_auth_headers, [task.id], "set_priority", "HIGH")
    history = (await client.get(f"/api/tasks/{task.id}/history", headers=manager_auth_headers)).json()["data"]
    assert any(h["action"] == "UPDATED" and h["changes"]["priority"]["new"] == "HIGH" for h in history)


async def test_requires_authentication(client: AsyncClient):
    assert (await client.post("/api/tasks/bulk", json={"task_ids": [str(uuid.uuid4())], "action": "complete"})).status_code == 401
