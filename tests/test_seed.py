"""
Test Database Seeding
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Task, TaskAuditLog, User
from db.seed import seed_data


@pytest.mark.asyncio
async def test_seed_execution(db_session: AsyncSession):
    """Verify seed_data creates the expected default users, tasks, and audit logs."""
    # Seed data into the test database session
    await seed_data(session=db_session)

    # Verify users created
    users_stmt = select(User)
    users = (await db_session.execute(users_stmt)).scalars().all()
    assert len(users) >= 3
    roles = {u.role for u in users}
    assert "admin" in roles
    assert "manager" in roles
    assert "employee" in roles

    # Verify tasks created
    tasks_stmt = select(Task)
    tasks = (await db_session.execute(tasks_stmt)).scalars().all()
    assert len(tasks) >= 5

    # Verify audit logs created and linked
    audit_stmt = select(TaskAuditLog)
    audits = (await db_session.execute(audit_stmt)).scalars().all()
    assert len(audits) >= 5
    for a in audits:
        assert a.action == "CREATED"
        assert a.source == "seed"


def test_seed_password_defaults_in_development(monkeypatch):
    from config import settings
    from db.seed import DEV_SEED_PASSWORD, resolve_seed_password

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.delenv("SEED_PASSWORD", raising=False)
    assert resolve_seed_password() == DEV_SEED_PASSWORD


def test_seed_refuses_weak_or_missing_password_in_production(monkeypatch):
    import pytest
    from config import settings
    from db.seed import resolve_seed_password

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.delenv("SEED_PASSWORD", raising=False)
    with pytest.raises(RuntimeError):
        resolve_seed_password()
    monkeypatch.setenv("SEED_PASSWORD", "short")
    with pytest.raises(RuntimeError):
        resolve_seed_password()
    monkeypatch.setenv("SEED_PASSWORD", "a-sufficiently-long-secret")
    assert resolve_seed_password() == "a-sufficiently-long-secret"


def test_seed_password_is_stripped(monkeypatch):
    from db.seed import resolve_seed_password

    monkeypatch.setenv("SEED_PASSWORD", "  a-long-enough-pass \n")
    assert resolve_seed_password() == "a-long-enough-pass"


async def test_demo_passwords_can_be_repaired(db_session, monkeypatch):
    """A deployment seeded with a stray newline in the password can be fixed without touching the DB."""
    from auth.jwt import get_password_hash, verify_password
    from db.seed import reset_demo_passwords, seed_data
    from sqlalchemy import select
    from db.models import User

    await seed_data(session=db_session)
    admin = (await db_session.execute(select(User).where(User.email == "admin@orbit.dev"))).scalar_one()
    admin.hashed_password = get_password_hash("correct-pass-123\n")  # what the stray newline produced
    await db_session.commit()
    assert not verify_password("correct-pass-123", admin.hashed_password)

    monkeypatch.setenv("SEED_PASSWORD", "correct-pass-123")
    assert await reset_demo_passwords(db_session) == 3
    await db_session.refresh(admin)
    assert verify_password("correct-pass-123", admin.hashed_password)
