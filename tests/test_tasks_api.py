"""
Tests for Phase 2: Tasks, Users, and Analytics REST APIs
"""

import uuid
from datetime import date, timedelta
import pytest
from httpx import AsyncClient

from db.models import User
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_task_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test POST /api/tasks creates task with audit log."""
    payload = {
        "title": "Build Frontend Dashboard",
        "description": "Create Next.js 14 Kanban board for tasks",
        "priority": "HIGH",
        "due_date": str(date.today() + timedelta(days=3)),
        "assignee_id": str(seed_test_user.id),
        "tags": ["frontend", "ui"],
    }
    response = await client.post(
        "/api/tasks", json=payload, headers=user_auth_headers
    )
    assert response.status_code == 201
    res = response.json()
    assert res["success"] is True
    assert res["data"]["title"] == "Build Frontend Dashboard"
    assert res["data"]["status"] == "TODO"
    assert res["data"]["priority"] == "HIGH"
    assert "id" in res["data"]


@pytest.mark.asyncio
async def test_list_and_filter_tasks_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test GET /api/tasks with query search and pagination."""
    # Create 2 tasks
    await client.post(
        "/api/tasks",
        json={"title": "Design Database Schema", "priority": "CRITICAL"},
        headers=user_auth_headers,
    )
    await client.post(
        "/api/tasks",
        json={"title": "Setup Docker compose", "priority": "MEDIUM"},
        headers=user_auth_headers,
    )

    # List all
    res = await client.get("/api/tasks", headers=user_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) >= 2
    assert "meta" in data
    assert data["meta"]["total"] >= 2

    # Search with q
    search_res = await client.get("/api/tasks?q=Database", headers=user_auth_headers)
    search_data = search_res.json()
    assert len(search_data["data"]) >= 1
    assert "Database" in search_data["data"][0]["title"]


@pytest.mark.asyncio
async def test_get_task_details_and_history(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test GET /api/tasks/{id} returns details and audit trail."""
    create_res = await client.post(
        "/api/tasks",
        json={"title": "Implement LangGraph agent", "priority": "HIGH"},
        headers=user_auth_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Get details
    detail_res = await client.get(
        f"/api/tasks/{task_id}", headers=user_auth_headers
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert detail["id"] == task_id
    assert len(detail["audit_logs"]) >= 1
    assert detail["audit_logs"][0]["action"] == "CREATED"

    # Get history endpoint
    history_res = await client.get(
        f"/api/tasks/{task_id}/history", headers=user_auth_headers
    )
    assert history_res.status_code == 200
    history = history_res.json()["data"]
    assert len(history) >= 1


@pytest.mark.asyncio
async def test_update_and_complete_task_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test PATCH /api/tasks/{id} and POST /api/tasks/{id}/complete."""
    create_res = await client.post(
        "/api/tasks",
        json={"title": "Write REST API", "priority": "LOW"},
        headers=user_auth_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Partial update
    patch_res = await client.patch(
        f"/api/tasks/{task_id}",
        json={"priority": "CRITICAL", "status": "IN_PROGRESS"},
        headers=user_auth_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["priority"] == "CRITICAL"
    assert patch_res.json()["data"]["status"] == "IN_PROGRESS"

    # Complete task
    complete_res = await client.post(
        f"/api/tasks/{task_id}/complete",
        json={"completion_note": "Finished all routes"},
        headers=user_auth_headers,
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["data"]["status"] == "DONE"
    assert complete_res.json()["data"]["completed_at"] is not None


@pytest.mark.asyncio
async def test_delete_task_role_permissions(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    manager_auth_headers: dict,
):
    """Test DELETE /api/tasks/{id} requires manager role."""
    create_res = await client.post(
        "/api/tasks",
        json={"title": "Temporary Task", "priority": "LOW"},
        headers=user_auth_headers,
    )
    task_id = create_res.json()["data"]["id"]

    # Attempt delete as employee (forbidden)
    emp_del = await client.delete(
        f"/api/tasks/{task_id}", headers=user_auth_headers
    )
    assert emp_del.status_code == 403

    # Delete as manager (success)
    mgr_del = await client.delete(
        f"/api/tasks/{task_id}", headers=manager_auth_headers
    )
    assert mgr_del.status_code == 200

    # Ensure soft deleted
    get_res = await client.get(
        f"/api/tasks/{task_id}", headers=user_auth_headers
    )
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_overdue_tasks_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test GET /api/tasks/overdue returns past-due items."""
    # Create overdue task
    await client.post(
        "/api/tasks",
        json={
            "title": "Old Task",
            "due_date": str(date.today() - timedelta(days=2)),
            "status": "TODO",
        },
        headers=user_auth_headers,
    )

    res = await client.get("/api/tasks/overdue", headers=user_auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) >= 1
    assert data[0]["days_overdue"] is not None
    assert data[0]["days_overdue"] > 0


@pytest.mark.asyncio
async def test_users_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test GET /api/users, GET /api/users/me, PATCH /api/users/me, and preferences."""
    # List users
    users_res = await client.get("/api/users", headers=user_auth_headers)
    assert users_res.status_code == 200
    assert len(users_res.json()["data"]) >= 1

    # Get me
    me_res = await client.get("/api/users/me", headers=user_auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["data"]["email"] == seed_test_user.email

    # Update profile
    patch_res = await client.patch(
        "/api/users/me",
        json={"display_name": "Updated Employee Name"},
        headers=user_auth_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["display_name"] == "Updated Employee Name"

    # Update preferences
    pref_res = await client.patch(
        "/api/users/me/preferences",
        json={"preferences": {"daily_briefing": "true", "briefing_time": "09:30"}},
        headers=user_auth_headers,
    )
    assert pref_res.status_code == 200


@pytest.mark.asyncio
async def test_analytics_api(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict, manager_auth_headers: dict
):
    """Test GET /api/analytics/stats and GET /api/analytics/team-workload with RBAC."""
    # Task stats (accessible by employee, scoped to self)
    stats_res = await client.get("/api/analytics/stats", headers=user_auth_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()["data"]
    assert "total_tasks" in stats
    assert "completed_tasks" in stats
    assert "completion_rate" in stats
    assert "tasks_by_priority" in stats

    # Team workload: Employee is forbidden (403)
    emp_workload_res = await client.get(
        "/api/analytics/team-workload", headers=user_auth_headers
    )
    assert emp_workload_res.status_code == 403

    # Team workload: Manager is authorized (200)
    workload_res = await client.get(
        "/api/analytics/team-workload", headers=manager_auth_headers
    )
    assert workload_res.status_code == 200
    workload = workload_res.json()["data"]
    assert isinstance(workload, list)


@pytest.mark.asyncio
async def test_task_creation_async_serialization_regression(
    db_session: AsyncSession, seed_test_user: User
):
    """Regression test: verify create_task eager-loads relationships so TaskRead serializes without MissingGreenlet."""
    from crud import tasks as task_crud
    from schemas.task import TaskCreate, TaskPriority, TaskRead

    task_in = TaskCreate(
        title="Async Relationship Serialization Test",
        description="Verify creator and assignee are eagerly loaded",
        priority=TaskPriority.HIGH,
        assignee_id=seed_test_user.id,
    )
    task = await task_crud.create_task(
        db=db_session,
        task_in=task_in,
        created_by_id=seed_test_user.id,
        source="regression_test",
    )

    # Validating into Pydantic schema TaskRead must succeed without MissingGreenlet
    task_read = TaskRead.model_validate(task)
    assert task_read.title == "Async Relationship Serialization Test"
    assert task_read.creator is not None
    assert task_read.creator.id == seed_test_user.id
    assert task_read.assignee is not None
    assert task_read.assignee.id == seed_test_user.id
