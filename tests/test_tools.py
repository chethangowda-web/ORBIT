"""
Unit Tests for Phase 3 Agent Tools
"""

import uuid
from datetime import date, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User
from tools import (
    complete_task,
    create_task,
    delete_task,
    format_task_card,
    get_all_users,
    get_overdue_tasks,
    get_task_by_id,
    get_task_stats,
    get_tasks_due_today,
    get_team_workload,
    get_user_by_name,
    get_user_tasks,
    search_tasks,
    update_task,
)


@pytest.mark.asyncio
async def test_create_and_resolve_task_tool(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Test create_task tool creates task and resolves assignee name."""
    res = await create_task.ainvoke(
        {
            "title": "Build Agent Tooling",
            "description": "LangChain tools for multi-agent system",
            "priority": "HIGH",
            "assignee_name": "Test Employee",
            "due_date": str(date.today() + timedelta(days=2)),
            "created_by_id": str(seed_manager_user.id),
            "tags": ["agents", "tools"],
        }
    )
    assert res["success"] is True
    data = res["data"]
    assert data["title"] == "Build Agent Tooling"
    assert data["priority"] == "HIGH"
    assert str(data["assignee_id"]) == str(seed_test_user.id)


@pytest.mark.asyncio
async def test_get_and_update_task_tool(
    db_session: AsyncSession, seed_test_user: User
):
    """Test get_task_by_id and update_task tools."""
    # Create task
    c_res = await create_task.ainvoke(
        {
            "title": "Initial Task",
            "created_by_id": str(seed_test_user.id),
        }
    )
    assert c_res["success"] is True
    task_id = c_res["data"]["id"]

    # Get by id
    g_res = await get_task_by_id.ainvoke({"task_id": task_id})
    assert g_res["success"] is True
    assert str(g_res["data"]["id"]) == str(task_id)
    assert len(g_res["data"]["audit_logs"]) >= 1

    # Update task
    u_res = await update_task.ainvoke(
        {
            "task_id": task_id,
            "title": "Updated Task Title",
            "priority": "CRITICAL",
            "status": "IN_PROGRESS",
            "updated_by_id": str(seed_test_user.id),
        }
    )
    assert u_res["success"] is True
    assert u_res["data"]["title"] == "Updated Task Title"
    assert u_res["data"]["priority"] == "CRITICAL"
    assert u_res["data"]["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_complete_and_delete_task_tool(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Test complete_task and delete_task tools.

    Deletion is manager/admin-only (auth.rbac.check_task_permission), so the
    delete step runs as a manager even though creation/completion is by the
    employee assignee.
    """
    c_res = await create_task.ainvoke(
        {
            "title": "Task To Complete And Delete",
            "created_by_id": str(seed_test_user.id),
        }
    )
    assert c_res["success"] is True
    task_id = c_res["data"]["id"]

    # Complete task
    comp_res = await complete_task.ainvoke(
        {
            "task_id": task_id,
            "completed_by_id": str(seed_test_user.id),
            "completion_note": "Verified by tester",
        }
    )
    assert comp_res["success"] is True
    assert comp_res["data"]["status"] == "DONE"
    assert comp_res["data"]["completed_at"] is not None

    # Delete task (manager/admin only)
    del_res = await delete_task.ainvoke(
        {
            "task_id": task_id,
            "deleted_by_id": str(seed_manager_user.id),
            "reason": "Test finished",
        }
    )
    assert del_res["success"] is True
    assert str(del_res["data"]["deleted_id"]) == str(task_id)


@pytest.mark.asyncio
async def test_search_and_query_task_tools(
    db_session: AsyncSession, seed_test_user: User
):
    """Test search_tasks, get_user_tasks, get_overdue_tasks, and get_tasks_due_today."""
    today = date.today()

    # Create active task
    await create_task.ainvoke(
        {
            "title": "Frontend optimization",
            "assignee_id": str(seed_test_user.id),
            "due_date": str(today),
            "created_by_id": str(seed_test_user.id),
        }
    )

    # Create overdue task
    await create_task.ainvoke(
        {
            "title": "Backend legacy migration",
            "assignee_id": str(seed_test_user.id),
            "due_date": str(today - timedelta(days=3)),
            "created_by_id": str(seed_test_user.id),
        }
    )

    # Search tasks
    s_res = await search_tasks.ainvoke({"query": "Frontend"})
    assert s_res["success"] is True
    assert len(s_res["data"]) >= 1

    # Get user tasks
    u_res = await get_user_tasks.ainvoke({"user_id": str(seed_test_user.id)})
    assert u_res["success"] is True
    assert len(u_res["data"]) >= 2

    # Get overdue tasks
    o_res = await get_overdue_tasks.ainvoke({"user_id": str(seed_test_user.id)})
    assert o_res["success"] is True
    assert len(o_res["data"]) >= 1
    assert any("migration" in t["title"] for t in o_res["data"])

    # Get tasks due today
    d_res = await get_tasks_due_today.ainvoke({"user_id": str(seed_test_user.id)})
    assert d_res["success"] is True
    assert len(d_res["data"]) >= 1


@pytest.mark.asyncio
async def test_user_and_analytics_tools(
    db_session: AsyncSession, seed_test_user: User, seed_manager_user: User
):
    """Test user lookup, team workload, and task stats tools."""
    # Get user by name
    name_res = await get_user_by_name.ainvoke({"name": "Test Employee"})
    assert name_res["success"] is True
    assert len(name_res["data"]) >= 1
    assert name_res["data"][0]["email"] == seed_test_user.email

    # Non-existent user returns error safely without throwing
    not_found = await get_user_by_name.ainvoke({"name": "NonExistentPerson12345"})
    assert not_found["success"] is False
    assert "No active user found" in not_found["error"]

    # Get all users
    all_res = await get_all_users.ainvoke({"limit": 100})
    assert all_res["success"] is True
    assert len(all_res["data"]) >= 2

    # Team workload
    wl_res = await get_team_workload.ainvoke({})
    assert wl_res["success"] is True
    assert len(wl_res["data"]) >= 2

    # Task stats
    stats_res = await get_task_stats.ainvoke({})
    assert stats_res["success"] is True
    assert "total_tasks" in stats_res["data"]
    assert "completion_rate" in stats_res["data"]


def test_format_task_card():
    """Test format_task_card generates valid Google Chat Card v2 structure."""
    sample_task = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "title": "Deploy Next.js App",
        "priority": "HIGH",
        "status": "IN_PROGRESS",
        "due_date": "2026-10-10",
        "tags": ["frontend", "deploy"],
        "assignee": {"display_name": "John Doe"},
    }
    card = format_task_card(sample_task)
    assert "cardsV2" in card
    card_body = card["cardsV2"][0]["card"]
    assert card_body["header"]["title"] == "Deploy Next.js App"
    assert "HIGH" in card_body["header"]["subtitle"]
    assert len(card_body["sections"][0]["widgets"]) == 3
    assert card_body["fixedFooter"]["primaryButton"]["text"] == "Mark Complete"
