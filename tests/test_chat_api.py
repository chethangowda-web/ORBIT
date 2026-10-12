"""Tests for Phase 2: AI Command Center (POST /api/chat/query)."""

import asyncio
import uuid
from datetime import date, timedelta
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Task, User
from schemas.task import TaskPriority, TaskStatus


@pytest.mark.asyncio
async def test_chat_query_authenticated_success(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Verify authenticated user can query ORBIT and receive structured response."""
    payload = {
        "message": "Show my pending tasks",
        "thread_id": "test-thread-1",
    }
    response = await client.post("/api/chat/query", json=payload, headers=user_auth_headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert "response" in data
    assert data["thread_id"] == "test-thread-1"
    assert "message_id" in data
    assert isinstance(data["suggested_actions"], list)
    assert isinstance(data["metadata"]["tool_calls_made"], list)
    assert data["metadata"]["active_agent"] == "task_agent"


@pytest.mark.asyncio
async def test_chat_query_unauthenticated_rejected(client: AsyncClient):
    """Verify unauthenticated requests are rejected with 401."""
    payload = {"message": "Plan my day"}
    response = await client.post("/api/chat/query", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_query_empty_or_whitespace_message_rejected(
    client: AsyncClient, user_auth_headers: dict
):
    """Verify empty or whitespace-only messages are rejected with 422."""
    # Empty string
    res1 = await client.post("/api/chat/query", json={"message": ""}, headers=user_auth_headers)
    assert res1.status_code == 422

    # Whitespace only
    res2 = await client.post("/api/chat/query", json={"message": "   "}, headers=user_auth_headers)
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_chat_query_creates_task_and_returns_referenced_tasks(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict, db_session: AsyncSession
):
    """Verify natural-language task creation returns structured referenced task and persists to DB."""
    payload = {
        "message": f"Create a critical priority task for {seed_test_user.display_name} to test API gateways",
        "thread_id": "creation-thread",
    }
    response = await client.post("/api/chat/query", json=payload, headers=user_auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "Created Task" in data["response"]
    assert len(data["referenced_tasks"]) >= 1
    ref = data["referenced_tasks"][0]
    assert "test api gateways" in ref["title"].lower()
    assert ref["priority"] == "CRITICAL"

    # Verify task in database
    tasks = (await db_session.execute(select(Task).where(Task.id == uuid.UUID(ref["id"])))).scalars().all()
    assert len(tasks) == 1
    assert tasks[0].status == "TODO"
    assert tasks[0].priority == "CRITICAL"
    assert "test api gateways" in tasks[0].title.lower()


@pytest.mark.asyncio
async def test_chat_query_confirmation_required_flow(
    client: AsyncClient,
    seed_manager_user: User,
    manager_auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify destructive actions require HITL confirmation before execution."""
    # Create task to delete
    test_task = Task(
        title="Old Login Legacy Code",
        priority=TaskPriority.LOW.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(test_task)
    await db_session.commit()
    await db_session.refresh(test_task)

    # Turn 1: Request deletion
    t1_res = await client.post(
        "/api/chat/query",
        json={"message": "Delete the old login legacy code task", "thread_id": "delete-thread"},
        headers=manager_auth_headers,
    )
    assert t1_res.status_code == 200
    t1_data = t1_res.json()["data"]
    assert t1_data["needs_confirmation"] is True
    assert "Confirm" in t1_data["suggested_actions"]

    # Verify task is NOT deleted yet
    task_check = (await db_session.execute(select(Task).where(Task.id == test_task.id))).scalar_one()
    assert task_check.deleted_at is None

    # Turn 2: Confirm deletion
    t2_res = await client.post(
        "/api/chat/query",
        json={
            "message": "yes",
            "thread_id": "delete-thread",
            "confirmed": True,
        },
        headers=manager_auth_headers,
    )
    assert t2_res.status_code == 200
    t2_data = t2_res.json()["data"]
    assert t2_data["needs_confirmation"] is False

    # Verify task is now deleted
    await db_session.refresh(task_check)
    assert task_check.deleted_at is not None


@pytest.mark.asyncio
async def test_chat_query_thread_and_user_isolation(
    client: AsyncClient,
    seed_test_user: User,
    seed_manager_user: User,
    user_auth_headers: dict,
    manager_auth_headers: dict,
):
    """Verify threads with identical client IDs are isolated across distinct users."""
    shared_thread_id = "shared-session-id"

    # User 1 queries
    res1 = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": shared_thread_id},
        headers=user_auth_headers,
    )
    assert res1.status_code == 200

    # User 2 queries with same thread_id
    res2 = await client.post(
        "/api/chat/query",
        json={"message": "What should I focus on today?", "thread_id": shared_thread_id},
        headers=manager_auth_headers,
    )
    assert res2.status_code == 200
    assert res2.json()["data"]["metadata"]["active_agent"] == "planner_agent"


@pytest.mark.asyncio
async def test_chat_query_agent_failure_safe_handling(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Verify internal agent exceptions or timeouts return safe formatted response without 500 error."""
    with patch("agents.orchestrator.get_compiled_graph", side_effect=Exception("Database lock simulated error")):
        response = await client.post(
            "/api/chat/query",
            json={"message": "Plan my day"},
            headers=user_auth_headers,
        )
        assert response.status_code == 200
        res = response.json()
        assert res["success"] is True
        data = res["data"]
        assert "something went wrong" in data["response"].lower()
        assert "database lock" not in data["response"].lower(), "internal error text must not reach the user"
        assert data["needs_confirmation"] is False
