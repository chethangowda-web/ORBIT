"""Task lifecycle, search, sorting and analytics correctness."""

from datetime import timedelta

from httpx import AsyncClient

from db.base import local_today, utc_now
from db.models import Task, User


async def _task(db, creator: User, assignee: User | None = None, **fields) -> Task:
    task = Task(
        title=fields.pop("title", "Task"),
        created_by_id=creator.id,
        assignee_id=assignee.id if assignee else None,
        **fields,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def test_invalid_sort_column_falls_back_instead_of_500(
    client: AsyncClient, seed_manager_user, manager_auth_headers
):
    for bad in ("audit_logs", "metadata", "tags", "nonsense"):
        response = await client.get(f"/api/tasks?sort_by={bad}", headers=manager_auth_headers)
        assert response.status_code == 200, bad


async def test_search_escapes_like_wildcards(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    await _task(db_session, seed_manager_user, title="100% coverage")
    await _task(db_session, seed_manager_user, title="plain task")

    response = await client.get("/api/tasks?q=%25", headers=manager_auth_headers)
    titles = [t["title"] for t in response.json()["data"]]
    assert titles == ["100% coverage"]


async def test_search_matches_tags(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    await _task(db_session, seed_manager_user, title="Ship it", tags=["deployment"])
    await _task(db_session, seed_manager_user, title="Other", tags=["docs"])

    response = await client.get("/api/tasks?q=deploy", headers=manager_auth_headers)
    assert [t["title"] for t in response.json()["data"]] == ["Ship it"]


async def test_completing_twice_is_idempotent(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    task = await _task(db_session, seed_manager_user, title="Finish me")
    first = await client.post(f"/api/tasks/{task.id}/complete", headers=manager_auth_headers)
    second = await client.post(f"/api/tasks/{task.id}/complete", headers=manager_auth_headers)
    assert first.status_code == second.status_code == 200

    history = await client.get(f"/api/tasks/{task.id}/history", headers=manager_auth_headers)
    completions = [h for h in history.json()["data"] if h["action"] == "COMPLETED"]
    assert len(completions) == 1


async def test_cancelled_task_cannot_be_completed(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    task = await _task(db_session, seed_manager_user, status="CANCELLED")
    response = await client.post(f"/api/tasks/{task.id}/complete", headers=manager_auth_headers)
    assert response.status_code == 409


async def test_reopening_a_done_task_clears_completed_at(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    task = await _task(db_session, seed_manager_user, status="DONE", completed_at=utc_now())
    response = await client.patch(
        f"/api/tasks/{task.id}", json={"status": "IN_PROGRESS"}, headers=manager_auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["completed_at"] is None


async def test_status_update_to_done_sets_completed_at(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    task = await _task(db_session, seed_manager_user)
    response = await client.patch(
        f"/api/tasks/{task.id}", json={"status": "DONE"}, headers=manager_auth_headers
    )
    assert response.json()["data"]["completed_at"] is not None


async def test_stats_are_real_aggregates(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    today = local_today()
    created = utc_now() - timedelta(days=4)
    await _task(db_session, seed_manager_user, status="TODO", priority="HIGH",
                due_date=today - timedelta(days=2))
    await _task(db_session, seed_manager_user, status="IN_PROGRESS", priority="LOW")
    await _task(db_session, seed_manager_user, status="DONE", priority="HIGH",
                created_at=created, completed_at=created + timedelta(days=2),
                due_date=today - timedelta(days=9))

    stats = (await client.get("/api/analytics/stats", headers=manager_auth_headers)).json()["data"]
    assert stats["total_tasks"] == 3
    assert stats["completed_tasks"] == 1
    assert stats["in_progress_tasks"] == 1
    assert stats["overdue_tasks"] == 1  # the DONE task is past due but closed
    assert stats["by_status"]["TODO"] == 1
    assert stats["by_priority"]["HIGH"] == 2
    assert stats["avg_completion_days"] == 2.0
    assert len(stats["tasks_created_per_day"]) == 14
    assert sum(d["count"] for d in stats["tasks_created_per_day"]) == 3


async def test_avg_completion_days_is_zero_without_completed_tasks(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    await _task(db_session, seed_manager_user)
    stats = (await client.get("/api/analytics/stats", headers=manager_auth_headers)).json()["data"]
    assert stats["avg_completion_days"] == 0.0


async def test_employee_stats_match_employee_task_scope(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    await _task(db_session, seed_manager_user, seed_test_user, title="assigned to me")
    await _task(db_session, seed_test_user, None, title="created by me")
    await _task(db_session, seed_manager_user, None, title="not mine")

    listing = await client.get("/api/tasks", headers=user_auth_headers)
    stats = (await client.get("/api/analytics/stats", headers=user_auth_headers)).json()["data"]
    assert listing.json()["meta"]["total"] == 2
    assert stats["total_tasks"] == 2


async def test_employee_cannot_query_another_users_stats(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    await _task(db_session, seed_manager_user, seed_manager_user)
    response = await client.get(
        f"/api/analytics/stats?user_id={seed_manager_user.id}", headers=user_auth_headers
    )
    assert response.json()["data"]["total_tasks"] == 0


async def test_team_workload_counts_per_member(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, manager_auth_headers
):
    today = local_today()
    await _task(db_session, seed_manager_user, seed_test_user, status="DONE", priority="HIGH")
    await _task(db_session, seed_manager_user, seed_test_user, status="TODO", priority="LOW",
                due_date=today - timedelta(days=1))
    await _task(db_session, seed_manager_user, seed_test_user, status="CANCELLED",
                due_date=today - timedelta(days=1))

    rows = (await client.get("/api/analytics/team-workload", headers=manager_auth_headers)).json()["data"]
    by_name = {r["display_name"]: r for r in rows}
    john = by_name["Test Employee"]
    assert john["assigned_tasks"] == 3
    assert john["completed_tasks"] == 1
    assert john["overdue_tasks"] == 1
    assert john["high_priority_tasks"] == 1
    assert john["completion_rate"] == 0.33
    assert by_name["Test Manager"]["assigned_tasks"] == 0


async def test_soft_deleted_tasks_excluded_from_stats(
    client: AsyncClient, db_session, seed_manager_user, manager_auth_headers
):
    await _task(db_session, seed_manager_user, deleted_at=utc_now())
    stats = (await client.get("/api/analytics/stats", headers=manager_auth_headers)).json()["data"]
    assert stats["total_tasks"] == 0
