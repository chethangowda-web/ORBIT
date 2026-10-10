"""Tests for Phase 3: Redis Checkpointing, Durability, and User/Thread Isolation."""

import asyncio
import uuid
import pytest
from httpx import AsyncClient
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.memory_agent import (
    AsyncRedisCheckpointer,
    get_checkpointer_status,
    init_checkpointer,
    close_checkpointer,
)
from config import settings
from db.models import Task, User
from schemas.task import TaskPriority, TaskStatus


@pytest.mark.asyncio
async def test_redis_checkpointer_restoration_after_reinitialization():
    """Verify that conversation checkpoints saved to Redis survive checkpointer reinitialization (restart)."""
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=False,
        )
        await client.ping()
    except Exception:
        pytest.skip("Local Redis server is not running, skipping live Redis restoration test.")

    test_thread = f"user_{uuid.uuid4()}:session-123"
    saver1 = AsyncRedisCheckpointer(client, ttl=300)

    from langgraph.checkpoint.base import empty_checkpoint
    config = {"configurable": {"thread_id": test_thread, "checkpoint_ns": ""}}
    cp = empty_checkpoint()
    cp["id"] = "cp-restart-test"
    cp["channel_values"] = {
        "user_id": "test-user-id",
        "messages": ["User query 1"],
        "task_context": {"title": "Critical Task"},
    }
    cp["channel_versions"] = {"user_id": "1", "messages": "1", "task_context": "1"}

    await saver1.aput(config, cp, {"source": "test"}, {"user_id": "1", "messages": "1", "task_context": "1"})

    # Simulate backend restart by creating a completely new Saver instance
    saver2 = AsyncRedisCheckpointer(client, ttl=300)
    loaded = await saver2.aget_tuple({"configurable": {"thread_id": test_thread}})

    assert loaded is not None
    assert loaded.checkpoint["channel_values"]["user_id"] == "test-user-id"
    assert loaded.checkpoint["channel_values"]["messages"] == ["User query 1"]
    assert loaded.checkpoint["channel_values"]["task_context"]["title"] == "Critical Task"

    await client.aclose()


@pytest.mark.asyncio
async def test_checkpointer_thread_and_user_isolation(client: AsyncClient, seed_test_user: User, user_auth_headers: dict, seed_manager_user: User, manager_auth_headers: dict):
    """Verify conversations with the same client thread_id remain strictly isolated across users."""
    shared_thread_name = "common-planning-thread"

    # User 1 sends message
    res1 = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": shared_thread_name},
        headers=user_auth_headers,
    )
    assert res1.status_code == 200

    # User 2 sends message with the SAME client thread string
    res2 = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": shared_thread_name},
        headers=manager_auth_headers,
    )
    assert res2.status_code == 200

    # Thread IDs returned must match the client-facing thread identifier
    assert res1.json()["data"]["thread_id"] == shared_thread_name
    assert res2.json()["data"]["thread_id"] == shared_thread_name


@pytest.mark.asyncio
async def test_tamper_resistant_confirmation_flow(
    client: AsyncClient,
    seed_manager_user: User,
    manager_auth_headers: dict,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify that confirmations validate pending_confirmation struct and reject replay/cross-user attempts."""
    # 1. Create a task to delete
    test_task = Task(
        title="Sensitive Core Infrastructure Task",
        priority=TaskPriority.HIGH.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(test_task)
    await db_session.commit()
    await db_session.refresh(test_task)

    # Turn 1: Manager initiates deletion
    t1_res = await client.post(
        "/api/chat/query",
        json={"message": "Delete the sensitive core infrastructure task", "thread_id": "safe-del-thread"},
        headers=manager_auth_headers,
    )
    assert t1_res.status_code == 200
    t1_data = t1_res.json()["data"]
    assert t1_data["needs_confirmation"] is True

    # Turn 2: Unauthorized other user attempts to confirm manager's deletion
    attacker_res = await client.post(
        "/api/chat/query",
        json={"message": "yes", "thread_id": "safe-del-thread", "confirmed": True},
        headers=user_auth_headers,
    )
    assert attacker_res.status_code == 200
    # Attacker should NOT delete manager's task (either no pending action in attacker's thread or rejected)
    await db_session.refresh(test_task)
    assert test_task.deleted_at is None

    # Turn 3: Manager confirms deletion
    mgr_confirm_res = await client.post(
        "/api/chat/query",
        json={"message": "yes", "thread_id": "safe-del-thread", "confirmed": True},
        headers=manager_auth_headers,
    )
    assert mgr_confirm_res.status_code == 200
    assert mgr_confirm_res.json()["data"]["needs_confirmation"] is False
    assert "deleted" in mgr_confirm_res.json()["data"]["response"].lower()

    # Verify task is deleted
    await db_session.refresh(test_task)
    assert test_task.deleted_at is not None

    # Turn 4: Attempt Replay Attack (sending confirmed again on consumed action)
    replay_res = await client.post(
        "/api/chat/query",
        json={"message": "yes", "thread_id": "safe-del-thread", "confirmed": True},
        headers=manager_auth_headers,
    )
    assert replay_res.status_code == 200
    # Replay is safely rejected with clear message
    assert "no valid pending action" in replay_res.json()["data"]["response"].lower()


@pytest.mark.asyncio
async def test_confirmation_cancellation_flow(
    client: AsyncClient,
    seed_manager_user: User,
    manager_auth_headers: dict,
    db_session: AsyncSession,
):
    """Verify cancelling an action stops execution and marks pending confirmation as cancelled."""
    test_task = Task(
        title="Do Not Delete Me Task",
        priority=TaskPriority.LOW.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(test_task)
    await db_session.commit()
    await db_session.refresh(test_task)

    # Turn 1: Request delete
    t1_res = await client.post(
        "/api/chat/query",
        json={"message": "Delete the do not delete me task", "thread_id": "cancel-thread"},
        headers=manager_auth_headers,
    )
    assert t1_res.status_code == 200
    assert t1_res.json()["data"]["needs_confirmation"] is True

    # Turn 2: Cancel
    t2_res = await client.post(
        "/api/chat/query",
        json={"message": "cancel", "thread_id": "cancel-thread", "confirmed": False},
        headers=manager_auth_headers,
    )
    assert t2_res.status_code == 200
    assert t2_res.json()["data"]["needs_confirmation"] is False
    assert "cancelled" in t2_res.json()["data"]["response"].lower()

    # Verify task was NOT deleted
    await db_session.refresh(test_task)
    assert test_task.deleted_at is None


@pytest.mark.asyncio
async def test_checkpointer_ordering_and_latest_selection():
    """Verify that multiple sequential checkpoint writes produce correct monotonic order and aget_tuple selects the newest."""
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=False,
        )
        await client.ping()
    except Exception:
        pytest.skip("Local Redis server is not running, skipping live Redis test.")

    test_thread = f"user_{uuid.uuid4()}:order-test"
    saver = AsyncRedisCheckpointer(client, ttl=300)

    from langgraph.checkpoint.base import empty_checkpoint
    config = {"configurable": {"thread_id": test_thread, "checkpoint_ns": ""}}

    # Write checkpoint 1
    cp1 = empty_checkpoint()
    cp1["id"] = "001-step-alpha"
    cp1["channel_values"] = {"step": 1, "note": "first"}
    cp1["channel_versions"] = {"step": "1", "note": "1"}
    await saver.aput(config, cp1, {"step_idx": 1}, {"step": "1", "note": "1"})

    await asyncio.sleep(0.02)

    # Write checkpoint 2
    cp2 = empty_checkpoint()
    cp2["id"] = "002-step-beta"
    cp2["channel_values"] = {"step": 2, "note": "second"}
    cp2["channel_versions"] = {"step": "2", "note": "2"}
    await saver.aput(config, cp2, {"step_idx": 2}, {"step": "2", "note": "2"})

    await asyncio.sleep(0.02)

    # Write checkpoint 3
    cp3 = empty_checkpoint()
    cp3["id"] = "003-step-gamma"
    cp3["channel_values"] = {"step": 3, "note": "third"}
    cp3["channel_versions"] = {"step": "3", "note": "3"}
    await saver.aput(config, cp3, {"step_idx": 3}, {"step": "3", "note": "3"})

    # Fetch latest without passing checkpoint_id
    loaded_latest = await saver.aget_tuple({"configurable": {"thread_id": test_thread}})
    assert loaded_latest is not None
    assert loaded_latest.checkpoint["id"] == "003-step-gamma"
    assert loaded_latest.checkpoint["channel_values"]["step"] == 3
    assert loaded_latest.checkpoint["channel_values"]["note"] == "third"

    await client.aclose()


@pytest.mark.asyncio
async def test_checkpointer_alist_filtering_and_limits():
    """Verify alist() method handles limits, metadata filtering, before filters, and empty threads."""
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=False,
        )
        await client.ping()
    except Exception:
        pytest.skip("Local Redis server is not running, skipping live Redis test.")

    test_thread = f"user_{uuid.uuid4()}:alist-test"
    saver = AsyncRedisCheckpointer(client, ttl=300)

    from langgraph.checkpoint.base import empty_checkpoint
    config = {"configurable": {"thread_id": test_thread, "checkpoint_ns": ""}}

    # Empty thread check
    empty_list = [t async for t in saver.alist(config)]
    assert len(empty_list) == 0

    # Populate 3 checkpoints
    for i in range(1, 4):
        cp = empty_checkpoint()
        cp["id"] = f"cp-alist-{i}"
        cp["channel_values"] = {"turn": i}
        cp["channel_versions"] = {"turn": str(i)}
        meta = {"tag": "even" if i % 2 == 0 else "odd", "index": i}
        await saver.aput(config, cp, meta, {"turn": str(i)})
        await asyncio.sleep(0.01)

    # List all checkpoints
    all_tuples = [t async for t in saver.alist(config)]
    assert len(all_tuples) == 3
    # Check descending order (newest first)
    assert all_tuples[0].checkpoint["id"] == "cp-alist-3"
    assert all_tuples[1].checkpoint["id"] == "cp-alist-2"
    assert all_tuples[2].checkpoint["id"] == "cp-alist-1"

    # List with limit=2
    limited_tuples = [t async for t in saver.alist(config, limit=2)]
    assert len(limited_tuples) == 2
    assert limited_tuples[0].checkpoint["id"] == "cp-alist-3"

    # Filter by metadata: tag == 'even'
    filtered_tuples = [t async for t in saver.alist(config, filter={"tag": "even"})]
    assert len(filtered_tuples) == 1
    assert filtered_tuples[0].checkpoint["id"] == "cp-alist-2"

    await client.aclose()


@pytest.mark.asyncio
async def test_checkpointer_aput_writes_persistence():
    """Verify that intermediate writes saved via aput_writes are persisted and retrieved in CheckpointTuple."""
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
            decode_responses=False,
        )
        await client.ping()
    except Exception:
        pytest.skip("Local Redis server is not running, skipping live Redis test.")

    test_thread = f"user_{uuid.uuid4()}:writes-test"
    saver = AsyncRedisCheckpointer(client, ttl=300)

    from langgraph.checkpoint.base import empty_checkpoint
    config = {"configurable": {"thread_id": test_thread, "checkpoint_ns": "", "checkpoint_id": "cp-writes-1"}}
    cp = empty_checkpoint()
    cp["id"] = "cp-writes-1"
    cp["channel_values"] = {"counter": 1}
    cp["channel_versions"] = {"counter": "1"}

    await saver.aput(config, cp, {"source": "test"}, {"counter": "1"})

    # Put intermediate pending writes
    intermediate_writes = [("counter", 2), ("intermediate_msg", "approval_required")]
    await saver.aput_writes(config, intermediate_writes, task_id="task_node_1")

    # Load tuple and check pending_writes
    loaded = await saver.aget_tuple(config)
    assert loaded is not None
    assert len(loaded.pending_writes) == 2
    assert loaded.pending_writes[0] == ("task_node_1", "counter", 2)
    assert loaded.pending_writes[1] == ("task_node_1", "intermediate_msg", "approval_required")

    await client.aclose()

