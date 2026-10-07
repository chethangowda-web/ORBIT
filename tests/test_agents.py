"""Comprehensive tests for LangGraph multi-agent system."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage, HumanMessage

from agents.intents import Intent
from agents.memory_agent import resolve_references
from agents.orchestrator import process_message
from agents.supervisor import classify_intent
from crud.tasks import get_task
from db.models import Task, User
from schemas.task import TaskPriority, TaskStatus
from tools.task_tools import create_task


@pytest.mark.asyncio
async def test_supervisor_intent_classification():
    """Verify supervisor intent classification accuracy and entity extraction."""
    # 1. Create task
    res1 = await classify_intent("Create a high priority task for John to deploy frontend by Friday")
    assert res1.intent == Intent.CREATE_TASK
    assert res1.task_context.priority == "HIGH"
    assert res1.task_context.assignee_name == "John"

    # 2. Plan day
    res2 = await classify_intent("What should I focus on today?")
    assert res2.intent == Intent.PLAN_DAY

    # 3. Overdue tasks
    res3 = await classify_intent("Show my overdue tasks")
    assert res3.intent == Intent.GET_OVERDUE_TASKS

    # 4. My tasks
    res4 = await classify_intent("Show my pending tasks")
    assert res4.intent == Intent.GET_MY_TASKS

    # 5. Delete task
    res5 = await classify_intent("Delete the old login page task")
    assert res5.intent == Intent.DELETE_TASK

    # 6. Recommendations
    res6 = await classify_intent("Give me productivity recommendations")
    assert res6.intent == Intent.GET_RECOMMENDATIONS

    # 7. Help
    res7 = await classify_intent("Help me understand what you can do")
    assert res7.intent == Intent.HELP


@pytest.mark.asyncio
async def test_task_agent_create_and_query(db_session: AsyncSession, seed_test_user: User):
    """Test task agent handling NL create and list commands."""
    msg = f"Create a critical priority task for {seed_test_user.display_name} to optimize database indexes"
    state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message=msg,
        session=db_session,
    )

    assert state.get("intent") == Intent.CREATE_TASK.value
    assert state.get("active_agent") == "task_agent"
    assert "create_task" in state.get("tool_calls_made", [])
    assert "Created Task" in state.get("response", "") or "✅" in state.get("response", "")

    # Query tasks
    list_state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message="Show my pending tasks",
        session=db_session,
    )
    assert list_state.get("intent") == Intent.GET_MY_TASKS.value
    assert "optimize database indexes" in list_state.get("response", "").lower()


@pytest.mark.asyncio
async def test_task_agent_complete_flow(db_session: AsyncSession, seed_test_user: User):
    """Test task completion via NL."""
    # Create task first
    t_res = await create_task.ainvoke({
        "title": "Deploy notification worker",
        "created_by_id": str(seed_test_user.id),
        "assignee_name": seed_test_user.display_name,
    })
    created_task = t_res["data"]

    # Mark as completed
    comp_state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message="Mark Deploy notification worker as completed",
        session=db_session,
    )

    assert comp_state.get("intent") == Intent.COMPLETE_TASK.value
    assert "completed" in comp_state.get("response", "").lower()

    # Verify in DB
    refreshed = await get_task(db_session, created_task["id"])
    assert refreshed is not None
    assert refreshed.status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_planner_agent_daily_plan(db_session: AsyncSession, seed_test_user: User):
    """Test planner agent synthesis of daily plan."""
    await create_task.ainvoke({
        "title": "Urgent Security Patch",
        "priority": "CRITICAL",
        "created_by_id": str(seed_test_user.id),
        "assignee_name": seed_test_user.display_name,
    })

    state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message="What should I focus on today?",
        session=db_session,
    )

    assert state.get("intent") == Intent.PLAN_DAY.value
    assert state.get("active_agent") == "planner_agent"
    assert "Daily Action Plan" in state.get("response", "")
    assert "Urgent Security Patch" in state.get("response", "")


@pytest.mark.asyncio
async def test_recommendation_agent_insights(db_session: AsyncSession, seed_test_user: User):
    """Test recommendation agent analytics and overdue reporting."""
    rec_state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message="Give me productivity recommendations",
        session=db_session,
    )

    assert rec_state.get("intent") == Intent.GET_RECOMMENDATIONS.value
    assert rec_state.get("active_agent") == "recommendation_agent"
    assert "Productivity Insights" in rec_state.get("response", "")


@pytest.mark.asyncio
async def test_review_agent_hitl_delete_flow(db_session: AsyncSession, seed_test_user: User):
    """Test HITL confirmation flow for task deletion."""
    t_res = await create_task.ainvoke({
        "title": "Temporary test item to delete",
        "created_by_id": str(seed_test_user.id),
        "assignee_name": seed_test_user.display_name,
    })
    target_id = t_res["data"]["id"]

    # 1. First attempt: requires confirmation
    del_state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message=f"Delete task {target_id}",
        confirmed=False,
        session=db_session,
    )

    assert del_state.get("active_agent") == "review_agent"
    assert del_state.get("needs_confirmation") is True
    assert "Confirmation Required" in del_state.get("response", "")

    # 2. Second attempt with confirmed=True
    conf_state = await process_message(
        user_id=str(seed_test_user.id),
        space_id="spaces/TESTSPACE",
        message=f"Delete task {target_id}",
        confirmed=True,
        session=db_session,
    )

    assert conf_state.get("needs_confirmation") is False
    assert "successfully deleted" in conf_state.get("response", "").lower()

    # Verify task is soft-deleted
    deleted_task = await get_task(db_session, target_id)
    assert deleted_task is None or deleted_task.deleted_at is not None


@pytest.mark.asyncio
async def test_memory_reference_resolution():
    """Test pronoun and context reference resolution across conversation turns."""
    messages = [
        HumanMessage(content="Create a task to build auth module"),
        AIMessage(content="Created Task #e9b3a0f1-1234-5678-9abc-def012345678 (Build auth module)"),
    ]

    resolved_id = resolve_references("Mark it as high priority", messages)
    assert resolved_id == "e9b3a0f1-1234-5678-9abc-def012345678"
