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

os.environ.setdefault("SCHEDULER_JOBSTORE", "memory")

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


from config import settings as _settings


@pytest.fixture(autouse=True)
def offline_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never call a real LLM provider from tests (RULES.md section 6).

    Set ORBIT_LIVE_LLM=1 to opt in to live calls for manual evaluation runs.
    """
    if os.environ.get("ORBIT_LIVE_LLM") == "1":
        return
    monkeypatch.setattr(_settings, "GOOGLE_GEMINI_API_KEY", "")
    monkeypatch.setattr(_settings, "OPENAI_API_KEY", "")


@pytest.fixture(autouse=True)
def block_google_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast instead of calling Google's APIs, and skip retry backoff sleeps."""
    import httpx
    import services.notifications as notifications

    real_send = httpx.AsyncClient.send

    async def guarded_send(self, request, **kwargs):
        if request.url.host.endswith("googleapis.com"):
            raise httpx.ConnectError("Google APIs are blocked in tests")
        return await real_send(self, request, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_send)
    monkeypatch.setattr(notifications, "RETRY_BACKOFF_SECONDS", 0)


@pytest.fixture
def allow_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enable public self-registration for tests that exercise it."""
    monkeypatch.setattr(_settings, "ALLOW_REGISTRATION", True)


@pytest.fixture(autouse=True)
def chat_auth_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests start with Chat verification off whatever the developer's .env says; tests that
    exercise verification switch it on explicitly."""
    monkeypatch.setattr(_settings, "GOOGLE_CHAT_VERIFY_AUTH", False)
    monkeypatch.setattr(_settings, "GOOGLE_CHAT_AUDIENCE", "")


@pytest.fixture(autouse=True)
def isolated_uploads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Attachments land in a per-test temp directory, never in the real uploads folder."""
    monkeypatch.setattr(_settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


@pytest.fixture(autouse=True)
def clean_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep login rate-limit counters in-process and isolated between tests."""
    import auth.ratelimit as ratelimit

    monkeypatch.setattr(ratelimit, "_get_redis", lambda: None)
    ratelimit.reset_memory_limits()


from tools.base import current_tool_session


@pytest_asyncio.fixture(scope="function", autouse=True)
async def bind_tool_session(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Automatically bind the active test session to tools."""
    token = current_tool_session.set(db_session)
    yield
    current_tool_session.reset(token)


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


@pytest_asyncio.fixture(scope="function")
async def seed_manager_user(db_session: AsyncSession) -> User:
    """Create a verified test manager in the test database."""
    user = User(
        email="manager@orbit.dev",
        hashed_password=get_password_hash("password123"),
        display_name="Test Manager",
        role="manager",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
def manager_auth_headers(seed_manager_user: User) -> dict:
    """Return Authorization header with valid JWT for the test manager."""
    token = create_access_token(
        data={
            "sub": str(seed_manager_user.id),
            "email": seed_manager_user.email,
            "role": seed_manager_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def seed_admin_user(db_session: AsyncSession) -> User:
    """Create a verified test admin in the test database."""
    user = User(
        email="admin@orbit.dev",
        hashed_password=get_password_hash("password123"),
        display_name="Test Admin",
        role="admin",
        timezone="Asia/Kolkata",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
def admin_auth_headers(seed_admin_user: User) -> dict:
    """Return Authorization header with valid JWT for the test admin."""
    token = create_access_token(
        data={
            "sub": str(seed_admin_user.id),
            "email": seed_admin_user.email,
            "role": seed_admin_user.role,
        }
    )
    return {"Authorization": f"Bearer {token}"}
