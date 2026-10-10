"""
Database Seeder Script
Populates initial roles, test users, sample tasks, and audit logs.
"""

import asyncio
import os
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt import get_password_hash
from config import settings
from db.base import Base, local_today, utc_now
from db.models import Task, TaskAuditLog, User
from db.session import async_session_factory, engine


DEV_SEED_PASSWORD = "password123"


def resolve_seed_password() -> str:
    """Password for seeded demo accounts.

    Development and tests use a well-known password. Production refuses to seed
    unless SEED_PASSWORD is supplied, so a default admin password can never ship.
    """
    configured = os.environ.get("SEED_PASSWORD", "")
    if settings.ENVIRONMENT.lower() == "production":
        if len(configured) < 12:
            raise RuntimeError(
                "Refusing to seed in production without SEED_PASSWORD (min 12 characters)."
            )
        return configured
    return configured or DEV_SEED_PASSWORD


async def populate_data(session: AsyncSession) -> None:
    """Populate default users and tasks within an active session."""
    result = await session.execute(select(User))
    existing_users = result.scalars().all()
    if existing_users:
        return

    pwd_hash = get_password_hash(resolve_seed_password())

    admin = User(
        email="admin@orbit.dev",
        hashed_password=pwd_hash,
        display_name="System Admin",
        first_name="System",
        last_name="Admin",
        role="admin",
        timezone="Asia/Kolkata",
        is_active=True,
    )

    manager = User(
        email="sarah@orbit.dev",
        hashed_password=pwd_hash,
        display_name="Sarah Connor",
        first_name="Sarah",
        last_name="Connor",
        role="manager",
        timezone="Asia/Kolkata",
        is_active=True,
    )

    employee = User(
        email="john@orbit.dev",
        hashed_password=pwd_hash,
        display_name="John Doe",
        first_name="John",
        last_name="Doe",
        role="employee",
        google_id="users/1029384756",
        google_space_id="spaces/AAAA1234",
        timezone="Asia/Kolkata",
        is_active=True,
    )

    session.add_all([admin, manager, employee])
    await session.commit()
    await session.refresh(admin)
    await session.refresh(manager)
    await session.refresh(employee)

    today = local_today()
    tasks_to_create = [
        Task(
            title="Deploy frontend v1.0",
            description="Coordinate rollout of Next.js frontend to production environment.",
            priority="HIGH",
            status="IN_PROGRESS",
            due_date=today + timedelta(days=3),
            created_by_id=manager.id,
            assignee_id=employee.id,
            tags=["deployment", "frontend"],
        ),
        Task(
            title="Implement JWT authentication",
            description="Secure API endpoints with Bearer tokens and role-based authorization.",
            priority="CRITICAL",
            status="DONE",
            due_date=today - timedelta(days=1),
            completed_at=utc_now(),
            created_by_id=admin.id,
            assignee_id=employee.id,
            tags=["auth", "backend"],
        ),
        Task(
            title="Review database indexing and query plans",
            description="Optimize partial indexes for tasks and audit logs.",
            priority="MEDIUM",
            status="TODO",
            due_date=today + timedelta(days=5),
            created_by_id=manager.id,
            assignee_id=employee.id,
            tags=["database", "performance"],
        ),
        Task(
            title="Setup Google Chat bot webhook integration",
            description="Handle interactive cards and text message intents from Google Chat.",
            priority="HIGH",
            status="TODO",
            due_date=today + timedelta(days=4),
            created_by_id=manager.id,
            assignee_id=employee.id,
            tags=["chat", "integration"],
        ),
        Task(
            title="Draft weekly summary report template",
            description="Template for Friday automated productivity briefings.",
            priority="LOW",
            status="TODO",
            due_date=today + timedelta(days=7),
            created_by_id=admin.id,
            assignee_id=manager.id,
            tags=["reporting"],
        ),
    ]

    session.add_all(tasks_to_create)
    await session.commit()

    for t in tasks_to_create:
        await session.refresh(t)
        audit = TaskAuditLog(
            task_id=t.id,
            user_id=t.created_by_id,
            action="CREATED",
            changes={"status": {"new": t.status}, "priority": {"new": t.priority}},
            source="seed",
        )
        session.add(audit)

    await session.commit()


async def seed_data(session: Optional[AsyncSession] = None) -> None:
    """Entrypoint to seed database with initial records."""
    if session is not None:
        await populate_data(session)
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as s:
        await populate_data(s)
        print("Database seed completed successfully!")


# Alias for compatibility
seed_database = seed_data


if __name__ == "__main__":
    asyncio.run(seed_data())
