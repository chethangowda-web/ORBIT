"""
Test Database Seeding
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, TaskAuditLog, User
from db.seed import seed_data


@pytest.mark.asyncio
async def test_seed_execution(db_session: AsyncSession, custom_session_factory, custom_engine):
    """Verify seed_data creates the expected default users and tasks."""
    # Seed data into test database
    await seed_data(session_factory=custom_session_factory, db_engine=custom_engine)

    # Verify users created
    users_stmt = select(User)
    users = (await db_session.execute(users_stmt)).scalars().all()
    assert len(users) >= 3

    # Verify tasks created
    tasks_stmt = select(Task)
    tasks = (await db_session.execute(tasks_stmt)).scalars().all()
    assert len(tasks) >= 5

    # Verify audit logs created
    audit_stmt = select(TaskAuditLog)
    audits = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(audits) >= 5
