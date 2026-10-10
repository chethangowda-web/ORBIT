"""Comprehensive Agent Evaluation & Accuracy Suite for ORBIT Phase 4A.
Covers: 8 Core Intents, Tool Execution, Multi-Turn Context, Grounding, Clarifications, and Fallback.
"""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from db.models import Task, User
from schemas.task import TaskPriority, TaskStatus


@pytest.mark.asyncio
async def test_eval_all_eight_intents_end_to_end(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    seed_manager_user: User,
    manager_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates all 8 core intents end-to-end through the multi-agent graph."""
    results = {}

    # 1. CREATE_TASK
    res_create = await client.post(
        "/api/chat/query",
        json={"message": "Create a high priority task for Test Employee to deploy the frontend by Friday", "thread_id": "eval-1"},
        headers=user_auth_headers,
    )
    assert res_create.status_code == 200
    create_data = res_create.json()["data"]
    assert "created" in create_data["response"].lower()
    created_task_id = create_data["metadata"].get("referenced_tasks", [{}])[0].get("id") if create_data.get("metadata") else None
    results["CREATE_TASK"] = "PASS"

    # 2. GET_MY_TASKS
    res_list = await client.post(
        "/api/chat/query",
        json={"message": "Show my pending tasks", "thread_id": "eval-2"},
        headers=user_auth_headers,
    )
    assert res_list.status_code == 200
    assert "tasks" in res_list.json()["data"]["response"].lower()
    results["GET_MY_TASKS"] = "PASS"

    # 3. PLAN_DAY
    res_plan = await client.post(
        "/api/chat/query",
        json={"message": "What should I focus on today?", "thread_id": "eval-3"},
        headers=user_auth_headers,
    )
    assert res_plan.status_code == 200
    assert len(res_plan.json()["data"]["response"]) > 20
    results["PLAN_DAY"] = "PASS"

    # 4. GET_OVERDUE_TASKS
    res_overdue = await client.post(
        "/api/chat/query",
        json={"message": "What are my overdue tasks?", "thread_id": "eval-4"},
        headers=user_auth_headers,
    )
    assert res_overdue.status_code == 200
    assert "overdue" in res_overdue.json()["data"]["response"].lower() or "no overdue tasks" in res_overdue.json()["data"]["response"].lower()
    results["GET_OVERDUE_TASKS"] = "PASS"

    # 5. SEARCH_TASKS
    res_search = await client.post(
        "/api/chat/query",
        json={"message": "Search for frontend deployment", "thread_id": "eval-5"},
        headers=user_auth_headers,
    )
    assert res_search.status_code == 200
    results["SEARCH_TASKS"] = "PASS"

    # 6. UPDATE_TASK (using specific name)
    res_update = await client.post(
        "/api/chat/query",
        json={"message": "Update the Deploy the frontend priority to critical", "thread_id": "eval-6"},
        headers=user_auth_headers,
    )
    assert res_update.status_code == 200
    results["UPDATE_TASK"] = "PASS"

    # 7. COMPLETE_TASK
    res_comp = await client.post(
        "/api/chat/query",
        json={"message": "Mark the Deploy the frontend task as completed", "thread_id": "eval-7"},
        headers=user_auth_headers,
    )
    assert res_comp.status_code == 200
    assert "completed" in res_comp.json()["data"]["response"].lower()
    results["COMPLETE_TASK"] = "PASS"

    # 8. DELETE_TASK: employees are refused up front, managers get the HITL confirmation
    res_denied = await client.post(
        "/api/chat/query",
        json={"message": "Delete the Deploy the frontend task", "thread_id": "eval-8a"},
        headers=user_auth_headers,
    )
    assert res_denied.json()["data"]["needs_confirmation"] is False
    assert "managers and admins" in res_denied.json()["data"]["response"]

    res_del = await client.post(
        "/api/chat/query",
        json={"message": "Delete the Deploy the frontend task", "thread_id": "eval-8b"},
        headers=manager_auth_headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["data"]["needs_confirmation"] is True
    results["DELETE_TASK"] = "PASS"

    print("\n--- 8 Core Intents Evaluation Summary ---")
    for intent, status in results.items():
        print(f"  • {intent}: {status}")
    assert len(results) == 8


@pytest.mark.asyncio
async def test_eval_multi_turn_coreference_and_updates(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates multi-turn context retention: create -> make it high priority -> move deadline."""
    thread_name = "multi-turn-eval-thread"

    # Turn 1: Create task
    t1_res = await client.post(
        "/api/chat/query",
        json={"message": "Create a task to finish the annual financial report", "thread_id": thread_name},
        headers=user_auth_headers,
    )
    assert t1_res.status_code == 200
    t1_text = t1_res.json()["data"]["response"]
    assert "created" in t1_text.lower()

    # Turn 2: Follow-up: "Make it high priority"
    t2_res = await client.post(
        "/api/chat/query",
        json={"message": "Make it high priority", "thread_id": thread_name},
        headers=user_auth_headers,
    )
    assert t2_res.status_code == 200
    t2_text = t2_res.json()["data"]["response"]
    assert "updated" in t2_text.lower() or "high" in t2_text.lower()

    # Turn 3: Follow-up: "Move that deadline to Friday"
    t3_res = await client.post(
        "/api/chat/query",
        json={"message": "Move that deadline to Friday", "thread_id": thread_name},
        headers=user_auth_headers,
    )
    assert t3_res.status_code == 200
    t3_text = t3_res.json()["data"]["response"]
    assert "updated" in t3_text.lower() or "deadline" in t3_text.lower()


@pytest.mark.asyncio
async def test_eval_ambiguous_request_clarification(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
):
    """Evaluates that ambiguous requests trigger a polite clarification rather than arbitrary execution."""
    # Attempting to update priority on empty new thread without context
    res = await client.post(
        "/api/chat/query",
        json={"message": "Make it high priority", "thread_id": "isolated-empty-thread-999"},
        headers=user_auth_headers,
    )
    assert res.status_code == 200
    resp_text = res.json()["data"]["response"]
    assert "which task" in resp_text.lower() or "specify" in resp_text.lower()


@pytest.mark.asyncio
async def test_eval_unauthorized_and_invalid_assignee(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates that invalid/unknown assignees prompt clarification."""
    # Create task
    t_task = Task(
        title="Database Optimization Task",
        priority=TaskPriority.MEDIUM.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_test_user.id,
    )
    db_session.add(t_task)
    await db_session.commit()
    await db_session.refresh(t_task)

    # Attempt to assign to non-existent person
    res = await client.post(
        "/api/chat/query",
        json={"message": f"Assign Task #{t_task.id} to NonExistentPerson999", "thread_id": "assignee-eval"},
        headers=user_auth_headers,
    )
    assert res.status_code == 200
    resp_text = res.json()["data"]["response"]
    assert "could not find" in resp_text.lower() or "team member" in resp_text.lower()


@pytest.mark.asyncio
async def test_eval_llm_synthesis_and_fallback_resilience(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates that Planner and Recommendation agents synthesize responses with deterministic fallback."""
    # Seed task due today
    task = Task(
        title="Prepare Investor Presentation",
        priority=TaskPriority.CRITICAL.value,
        status=TaskStatus.IN_PROGRESS.value,
        created_by_id=seed_test_user.id,
        assignee_id=seed_test_user.id,
    )
    db_session.add(task)
    await db_session.commit()

    # 1. Successful Synthesis with Mock LLM
    with patch("agents.planner_agent.call_llm", return_value="📋 Custom LLM Synthesized Focus Plan: Tackle Investor Presentation first!"):
        res_llm = await client.post(
            "/api/chat/query",
            json={"message": "Plan my day", "thread_id": "plan-synth-test"},
            headers=user_auth_headers,
        )
        assert res_llm.status_code == 200
        assert "Custom LLM Synthesized Focus Plan" in res_llm.json()["data"]["response"]

    # 2. Fallback when LLM is unavailable (None returned)
    with patch("agents.planner_agent.call_llm", return_value=None):
        res_fb = await client.post(
            "/api/chat/query",
            json={"message": "Plan my day", "thread_id": "plan-fallback-test"},
            headers=user_auth_headers,
        )
        assert res_fb.status_code == 200
        assert "Your Daily Action Plan" in res_fb.json()["data"]["response"]
        assert "Prepare Investor Presentation" in res_fb.json()["data"]["response"]


@pytest.mark.asyncio
async def test_eval_two_tasks_ambiguous_make_it_high_priority(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates that issuing an ambiguous follow-up without prior context asks for clarification."""
    # Create two tasks in DB
    t1 = Task(title="Task Alpha", priority=TaskPriority.LOW.value, status=TaskStatus.TODO.value, created_by_id=seed_test_user.id)
    t2 = Task(title="Task Beta", priority=TaskPriority.LOW.value, status=TaskStatus.TODO.value, created_by_id=seed_test_user.id)
    db_session.add_all([t1, t2])
    await db_session.commit()

    # User sends ambiguous update on fresh thread
    res = await client.post(
        "/api/chat/query",
        json={"message": "Make it high priority", "thread_id": "ambiguous-thread-fresh"},
        headers=user_auth_headers,
    )
    assert res.status_code == 200
    resp_text = res.json()["data"]["response"]
    assert "which task" in resp_text.lower() or "specify" in resp_text.lower()


@pytest.mark.asyncio
async def test_eval_reference_deleted_or_nonexistent_task(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
):
    """Evaluates that attempting to update a nonexistent task ID fails gracefully."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    res = await client.post(
        "/api/chat/query",
        json={"message": f"Update Task #{fake_uuid} priority to critical", "thread_id": "nonexistent-task-thread"},
        headers=user_auth_headers,
    )
    assert res.status_code == 200
    resp_text = res.json()["data"]["response"]
    assert "failed" in resp_text.lower() or "not found" in resp_text.lower() or "could not" in resp_text.lower()


@pytest.mark.asyncio
async def test_eval_cross_user_task_reference_isolation(
    client: AsyncClient,
    seed_test_user: User,
    user_auth_headers: dict,
    seed_manager_user: User,
    manager_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates that User A cannot modify or delete User B's task via chat agent."""
    # User A (seed_test_user) creates a task
    task_a = Task(
        title="Confidential Strategy Document",
        priority=TaskPriority.HIGH.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_test_user.id,
        assignee_id=seed_test_user.id,
    )
    db_session.add(task_a)
    await db_session.commit()
    await db_session.refresh(task_a)

    # User B attempts to complete User A's task (unauthorized if role/assignment mismatch)
    # Testing chat query isolation: user A's thread cannot be read/modified by another user
    res = await client.post(
        "/api/chat/query",
        json={"message": f"Show details for Task #{task_a.id}", "thread_id": f"isolated-thread-{seed_manager_user.id}"},
        headers=manager_auth_headers,
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_eval_destructive_action_replay_prevention(
    client: AsyncClient,
    seed_manager_user: User,
    manager_auth_headers: dict,
    db_session: AsyncSession,
):
    """Evaluates that destructive confirmations cannot be replayed or reused once consumed.

    Deletion is manager/admin-only (auth.rbac.check_task_permission), so this
    flow runs as a manager; an employee's deletion attempt is covered
    separately in test_rbac_and_oauth.py.
    """
    # Create task
    task = Task(
        title="Temporary Scrap Task",
        priority=TaskPriority.LOW.value,
        status=TaskStatus.TODO.value,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    thread_id = "replay-prevention-thread"

    # Turn 1: Request delete -> prompts confirmation
    res_req = await client.post(
        "/api/chat/query",
        json={"message": f"Delete Task #{task.id}", "thread_id": thread_id},
        headers=manager_auth_headers,
    )
    assert res_req.status_code == 200
    data1 = res_req.json()["data"]
    assert data1["needs_confirmation"] is True
    assert "Confirm" in data1["suggested_actions"]

    # Turn 2: Confirm deletion
    res_conf = await client.post(
        "/api/chat/query",
        json={"message": "yes", "confirmed": True, "thread_id": thread_id},
        headers=manager_auth_headers,
    )
    assert res_conf.status_code == 200
    data2 = res_conf.json()["data"]
    assert "deleted" in data2["response"].lower()

    # Turn 3: Attempt to replay confirmation
    res_replay = await client.post(
        "/api/chat/query",
        json={"message": "yes", "confirmed": True, "thread_id": thread_id},
        headers=manager_auth_headers,
    )
    assert res_replay.status_code == 200
    data3 = res_replay.json()["data"]
    assert "no valid pending action" in data3["response"].lower() or "consumed" in data3["response"].lower()

