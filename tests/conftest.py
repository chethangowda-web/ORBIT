"""
Pytest Fixtures for ORBIT Test Suite
Provides test database, test client, and authenticated user fixtures.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Ensure backend directory is in python sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from auth.jwt import create_access_token, get_password_hash
from db.base import Base
from db.models import User
from db.session import get_db
from main import app

# Test SQLite in-memory async database
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_async_session_factory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create fresh database tables and yield an isolated session per test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_async_session_factory() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client overriding get_db dependency with test database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def seed_test_user(db_session: AsyncSession) -> User:
    """Create a verified test employee in the test database."""
    user = User(
        email="testuser@orbit.dev",
        hashed_password=get_password_hash("password123"),
        display_name="Test Employee",
        role="employee",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
def user_auth_headers(seed_test_user: User) -> dict:
    """Return Authorization header with valid JWT for the test user."""
    token = create_access_token(
        data={
            "sub": str(seed_test_user.id),
            "email": seed_test_user.email,
            "role": seed_test_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}
