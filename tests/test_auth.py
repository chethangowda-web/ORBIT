"""
Tests for Phase 1 Authentication & Health APIs
"""

import pytest
from httpx import AsyncClient
from db.models import User


@pytest.mark.asyncio
async def test_health_api(client: AsyncClient):
    """Test health check endpoint reports database connected."""
    response = client.get("/api/health")
    if hasattr(response, "__await__"):
        response = await response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["database"] == "connected"


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_test_user: User):
    """Test login with valid email and password returns JWT token."""
    response = await client.post(
        "/api/auth/token",
        json={"email": "testuser@orbit.dev", "password": "password123"},
    )
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "testuser@orbit.dev"
    assert data["user"]["role"] == "employee"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, seed_test_user: User):
    """Test login with incorrect password returns 401 error."""
    response = await client.post(
        "/api/auth/token",
        json={"email": "testuser@orbit.dev", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    res = response.json()
    assert res["success"] is False
    assert "Invalid email or password" in res["error"]


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test registering a new user succeeds and issues token."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "newemployee@orbit.dev",
            "password": "strongpassword",
            "display_name": "New Employee",
            "role": "employee",
            "timezone": "Asia/Kolkata",
        },
    )
    assert response.status_code == 201
    res = response.json()
    assert res["success"] is True
    assert "access_token" in res["data"]
    assert res["data"]["user"]["display_name"] == "New Employee"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, seed_test_user: User):
    """Test registering with an existing email returns 409 conflict."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "testuser@orbit.dev",
            "password": "password123",
            "display_name": "Duplicate User",
            "role": "employee",
        },
    )
    assert response.status_code == 409
    res = response.json()
    assert res["success"] is False
    assert "already exists" in res["error"]


@pytest.mark.asyncio
async def test_get_current_user_profile(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict
):
    """Test GET /api/auth/me returns the authenticated profile."""
    response = await client.get("/api/auth/me", headers=user_auth_headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["data"]["email"] == seed_test_user.email
    assert res["data"]["display_name"] == seed_test_user.display_name


@pytest.mark.asyncio
async def test_get_profile_unauthorized(client: AsyncClient):
    """Test GET /api/auth/me without token returns 401."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
    res = response.json()
    assert res["success"] is False
