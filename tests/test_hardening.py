"""Security and robustness regressions for the hardened backend."""

import pytest
from httpx import AsyncClient

from config import Settings, settings


async def test_registration_disabled_by_default(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={"email": "x@orbit.dev", "password": "longenough123", "display_name": "X"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["error"]


async def test_register_enforces_password_length(client: AsyncClient, allow_registration):
    response = await client.post(
        "/api/auth/register",
        json={"email": "x@orbit.dev", "password": "short", "display_name": "X"},
    )
    assert response.status_code == 422


async def test_login_rate_limit_blocks_bruteforce(client: AsyncClient, seed_test_user, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 3)
    payload = {"email": "testuser@orbit.dev", "password": "wrong-password"}
    statuses = [(await client.post("/api/auth/token", json=payload)).status_code for _ in range(5)]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3:] == [429, 429]


async def test_login_rate_limit_is_per_email(client: AsyncClient, seed_test_user, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)
    for _ in range(3):
        await client.post("/api/auth/token", json={"email": "testuser@orbit.dev", "password": "bad"})
    other = await client.post("/api/auth/token", json={"email": "other@orbit.dev", "password": "bad"})
    assert other.status_code == 401


async def test_login_email_is_case_insensitive(client: AsyncClient, seed_test_user):
    response = await client.post(
        "/api/auth/token", json={"email": "TestUser@Orbit.dev", "password": "password123"}
    )
    assert response.status_code == 200


def test_production_rejects_unsafe_defaults():
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(ENVIRONMENT="production")


def test_production_accepts_safe_configuration():
    cfg = Settings(
        ENVIRONMENT="production",
        JWT_SECRET_KEY="x" * 48,
        CORS_ORIGINS=["https://orbit.example.com"],
        GOOGLE_CHAT_VERIFY_AUTH=True,
        GOOGLE_CHAT_AUDIENCE="123456789012",
    )
    assert cfg.ENVIRONMENT == "production"


def test_default_cors_has_no_wildcard():
    assert "*" not in Settings().CORS_ORIGINS


def test_production_rejects_placeholder_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="change-this-in-production-super-secret-jwt-key-orbit-2026",
            CORS_ORIGINS=["https://orbit.example.com"],
            GOOGLE_CHAT_VERIFY_AUTH=True,
            GOOGLE_CHAT_AUDIENCE="123456789012",
        )


def test_production_requires_audience_when_verifying_chat():
    with pytest.raises(ValueError, match="GOOGLE_CHAT_AUDIENCE"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="x" * 48,
            CORS_ORIGINS=["https://orbit.example.com"],
            GOOGLE_CHAT_VERIFY_AUTH=True,
            GOOGLE_CHAT_AUDIENCE="",
        )
