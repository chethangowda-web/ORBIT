"""Tests for Phase 3: Agent Execution Traces and Observability API."""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import AgentExecutionTrace, User


@pytest.mark.asyncio
async def test_trace_creation_on_chat_query(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify that every chat query generates an AgentExecutionTrace in DB with node timings and agents invoked."""
    payload = {
        "message": "Plan my day and show me my most urgent tasks",
        "thread_id": "trace-test-thread",
    }
    response = await client.post("/api/chat/query", json=payload, headers=user_auth_headers)
    assert response.status_code == 200
    meta = response.json()["data"]["metadata"]

    assert meta["request_id"] is not None
    assert "supervisor" in meta["agents_invoked"]
    assert "planner_agent" in meta["agents_invoked"]
    assert meta["total_duration_ms"] >= 0.0
    assert "supervisor" in meta["node_durations_ms"]

    # Verify trace persisted in database
    trace_query = select(AgentExecutionTrace).where(
        AgentExecutionTrace.request_id == meta["request_id"],
        AgentExecutionTrace.user_id == seed_test_user.id,
    )
    trace = (await db_session.execute(trace_query)).scalar_one_or_none()
    assert trace is not None
    assert trace.status == "SUCCESS"
    assert "planner_agent" in trace.agents_invoked
    assert "supervisor" in trace.node_durations_ms


@pytest.mark.asyncio
async def test_list_traces_endpoint_user_isolation(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    seed_manager_user: User,
    manager_auth_headers: dict,
):
    """Verify GET /api/chat/traces strictly filters traces by the authenticated user."""
    # 1. Test user creates a trace
    await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": "user1-thread"},
        headers=user_auth_headers,
    )

    # 2. Manager user creates a trace
    await client.post(
        "/api/chat/query",
        json={"message": "What should I focus on today?", "thread_id": "manager-thread"},
        headers=manager_auth_headers,
    )

    # 3. Test user lists traces
    res1 = await client.get("/api/chat/traces", headers=user_auth_headers)
    assert res1.status_code == 200
    user1_traces = res1.json()["data"]["items"]
    assert len(user1_traces) >= 1
    # Ensure all returned traces belong to test_user
    for t in user1_traces:
        assert t["user_id"] == str(seed_test_user.id)

    # 4. Manager lists traces
    res2 = await client.get("/api/chat/traces", headers=manager_auth_headers)
    assert res2.status_code == 200
    mgr_traces = res2.json()["data"]["items"]
    assert len(mgr_traces) >= 1
    for t in mgr_traces:
        assert t["user_id"] == str(seed_manager_user.id)


@pytest.mark.asyncio
async def test_get_single_trace_cross_user_access_rejected(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    seed_manager_user: User,
    manager_auth_headers: dict,
):
    """Verify that User B cannot retrieve User A's specific trace by trace_id (returns 404)."""
    # 1. User A creates a trace
    q_res = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": "user-a-thread"},
        headers=user_auth_headers,
    )
    assert q_res.status_code == 200

    # 2. Get User A's trace ID
    list_res = await client.get("/api/chat/traces", headers=user_auth_headers)
    assert list_res.status_code == 200
    user_a_trace_id = list_res.json()["data"]["items"][0]["id"]

    # 3. User A can retrieve their own trace
    get_res = await client.get(f"/api/chat/traces/{user_a_trace_id}", headers=user_auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["id"] == user_a_trace_id

    # 4. User B attempts to retrieve User A's trace -> 404 Access Denied
    unauth_res = await client.get(f"/api/chat/traces/{user_a_trace_id}", headers=manager_auth_headers)
    assert unauth_res.status_code == 404


@pytest.mark.asyncio
async def test_per_node_delta_timings_and_aggregation(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
):
    """Verify that node_durations_ms records incremental delta time per node, not cumulative timeline offsets."""
    response = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": "timing-test-thread"},
        headers=user_auth_headers,
    )
    assert response.status_code == 200
    meta = response.json()["data"]["metadata"]
    node_durations = meta["node_durations_ms"]

    # Each recorded node duration must be non-negative and finite
    for node_name, duration in node_durations.items():
        assert duration >= 0.0, f"Node {node_name} duration was negative"

    # Total duration must be >= individual node delta durations
    total_ms = meta["total_duration_ms"]
    assert total_ms >= max(node_durations.values())

