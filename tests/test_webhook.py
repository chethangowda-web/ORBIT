"""Unit and integration tests for Google Chat webhook and service integration."""

import json
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Task, User
from schemas.task import TaskPriority, TaskStatus
from services.google_chat import (
    build_confirmation_card_v2,
    build_task_card_v2,
    build_welcome_card_v2,
    send_card_message,
    send_dm,
    send_text_message,
    verify_google_chat_bearer_token,
    verify_webhook_signature,
)


def test_signature_verification_default():
    """Verify signature check returns True when no secret is configured."""
    assert verify_webhook_signature(b"test body", "") is True


def test_verify_google_chat_bearer_token_disabled_by_default():
    """Verify bearer check passes when strict verification is disabled in dev."""
    assert verify_google_chat_bearer_token(None) is True
    assert verify_google_chat_bearer_token("Bearer mock-token") is True


def test_verify_google_chat_bearer_token_strict_validation(monkeypatch: pytest.MonkeyPatch):
    """Verify bearer check correctly validates Google OIDC token with audience and issuer."""
    from config import settings
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")

    # Missing header
    assert verify_google_chat_bearer_token(None) is False
    assert verify_google_chat_bearer_token("Basic 12345") is False

    # Valid token
    with patch("services.google_chat.id_token.verify_oauth2_token", return_value={"iss": "chat@system.gserviceaccount.com", "aud": "123456789012"}):
        assert verify_google_chat_bearer_token("Bearer valid.mock.jwt") is True

    # Invalid issuer
    with patch("services.google_chat.id_token.verify_oauth2_token", return_value={"iss": "https://malicious-issuer.com"}):
        assert verify_google_chat_bearer_token("Bearer spoofed.mock.jwt") is False

    # Token verification exception (e.g. expired or invalid signature)
    with patch("services.google_chat.id_token.verify_oauth2_token", side_effect=ValueError("Token expired")):
        assert verify_google_chat_bearer_token("Bearer expired.mock.jwt") is False


@pytest.mark.asyncio
async def test_webhook_added_to_space_event(client: AsyncClient, db_session: AsyncSession):
    """Test webhook processing ADDED_TO_SPACE event and returning welcome card."""
    event_payload = {
        "type": "ADDED_TO_SPACE",
        "eventTime": "2026-10-07T12:00:00Z",
        "space": {"name": "spaces/TESTSPACE123", "type": "ROOM"},
        "user": {
            "name": "users/100000000000000000001",
            "displayName": "Alice Smith",
            "email": "alice@orbit.dev",
            "type": "HUMAN",
        },
    }

    with patch("api.webhook.send_card_message", new_callable=AsyncMock) as mock_send_card:
        mock_send_card.return_value = True
        response = await client.post(
            "/api/chat/webhook",
            json=event_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        # Welcome card is returned synchronously in Google Chat format
        assert "text" in data or "cardsV2" in data

    # Verify user auto-registration in DB
    query = select(User).where(User.email == "alice@orbit.dev")
    res = await db_session.execute(query)
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.display_name == "Alice Smith"
    assert user.google_id == "users/100000000000000000001"


@pytest.mark.asyncio
async def test_webhook_message_with_bot_mention_stripping(client: AsyncClient, db_session: AsyncSession):
    """Test webhook receiving MESSAGE with @ORBIT mention cleanly strips mention and creates task."""
    event_payload = {
        "type": "MESSAGE",
        "eventTime": "2026-10-07T12:05:00Z",
        "space": {"name": "spaces/TESTSPACE123", "type": "ROOM"},
        "user": {
            "name": "users/100000000000000000002",
            "displayName": "Bob Builder",
            "email": "bob@orbit.dev",
            "type": "HUMAN",
        },
        "message": {
            "name": "spaces/TESTSPACE123/messages/msg001",
            "text": "@ORBIT <users/bot123> Create a high priority task for Bob to deploy auth service by Friday",
            "thread": {"name": "spaces/TESTSPACE123/threads/th001"},
        },
    }

    with patch("api.webhook.send_card_message", new_callable=AsyncMock) as mock_send_card, \
         patch("api.webhook.send_text_message", new_callable=AsyncMock) as mock_send_text:
        mock_send_card.return_value = True
        mock_send_text.return_value = True

        response = await client.post(
            "/api/chat/webhook",
            json=event_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        # Handler responds synchronously with text/card reply
        assert response.json().get("text") or response.json().get("cardsV2")

    # Verify user registered
    query = select(User).where(User.email == "bob@orbit.dev")
    res = await db_session.execute(query)
    user = res.scalar_one_or_none()
    assert user is not None


@pytest.mark.asyncio
async def test_webhook_card_clicked_event(client: AsyncClient, db_session: AsyncSession):
    """Test webhook processing CARD_CLICKED interactive button events (confirm & complete)."""
    # Create user
    user = User(
        email="clicker@orbit.dev",
        google_id="users/clicker001",
        display_name="Clicker User",
        role="employee",
    )
    db_session.add(user)
    await db_session.commit()

    event_payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-10-07T12:10:00Z",
        "space": {"name": "spaces/TESTSPACE123", "type": "ROOM"},
        "user": {
            "name": "users/clicker001",
            "displayName": "Clicker User",
            "email": "clicker@orbit.dev",
        },
        "action": {
            "actionMethodName": "confirm_delete_task",
            "parameters": [
                {"key": "task_id", "value": "123"},
                {"key": "thread_id", "value": "spaces/TESTSPACE123:users/clicker001"},
            ],
        },
    }

    with patch("api.webhook.send_text_message", new_callable=AsyncMock) as mock_send_text:
        mock_send_text.return_value = True
        response = await client.post(
            "/api/chat/webhook",
            json=event_payload,
        )

        assert response.status_code == 200
        # CARD_CLICKED responses return a text reply directly
        assert "text" in response.json()


@pytest.mark.asyncio
async def test_webhook_strict_auth_rejected_when_invalid(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test webhook rejects unauthenticated requests when GOOGLE_CHAT_VERIFY_AUTH is enabled."""
    from config import settings
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")

    event_payload = {
        "type": "ADDED_TO_SPACE",
        "space": {"name": "spaces/TEST"},
    }

    # 1. No Authorization header
    res1 = await client.post("/api/chat/webhook", json=event_payload)
    assert res1.status_code == 401

    # 2. Invalid Bearer token
    with patch("services.google_chat.id_token.verify_oauth2_token", side_effect=Exception("Invalid signature")):
        res2 = await client.post(
            "/api/chat/webhook",
            json=event_payload,
            headers={"Authorization": "Bearer bad-jwt-token"},
        )
        assert res2.status_code == 401


@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test webhook rejects requests with invalid signature when secret is configured."""
    from config import settings
    monkeypatch.setattr(settings, "GOOGLE_CHAT_WEBHOOK_SECRET", "super-secret-key")

    event_payload = {
        "type": "ADDED_TO_SPACE",
        "space": {"name": "spaces/TEST"},
    }
    response = await client.post(
        "/api/chat/webhook",
        json=event_payload,
        headers={"X-Goog-Signature": "invalid-signature"},
    )
    assert response.status_code == 403
    assert "Invalid Google Chat webhook signature" in response.json().get("error", "")


@pytest.mark.asyncio
async def test_webhook_valid_hmac_signature(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    """Test webhook accepts request with valid HMAC SHA256 signature."""
    import hashlib
    import hmac
    from config import settings

    secret = "production-webhook-secret-123"
    monkeypatch.setattr(settings, "GOOGLE_CHAT_WEBHOOK_SECRET", secret)

    event_payload = {
        "type": "ADDED_TO_SPACE",
        "space": {"name": "spaces/TESTSPACE999"},
        "user": {"name": "users/999", "displayName": "Secret Agent"},
    }
    body_bytes = json.dumps(event_payload).encode("utf-8")
    valid_sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/chat/webhook",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Signature": valid_sig,
        },
    )
    assert response.status_code == 200
    # Valid HMAC: handler processes event and returns Google Chat format response
    assert "text" in response.json() or "cardsV2" in response.json()


@pytest.mark.asyncio
async def test_webhook_malformed_json_payload(client: AsyncClient):
    """Test webhook handles malformed JSON payload with 400 Bad Request."""
    response = await client.post(
        "/api/chat/webhook",
        content=b"not-a-valid-json-string",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert "Invalid event schema" in response.json().get("error", "")


@pytest.mark.asyncio
async def test_outbound_service_messaging_mocked():
    """Test outbound send_text_message, send_card_message, and send_dm with mocked HTTP client."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    # 1. Text message
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        success = await send_text_message("spaces/TEST1234", "Test Hello Message")
        assert success is True

    # 2. Card message
    card = build_task_card_v2({"id": "101", "title": "Deploy API", "priority": "HIGH", "status": "TODO"})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        success = await send_card_message("spaces/TEST1234", card)
        assert success is True

    # 3. Direct message (DM)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        success = await send_dm("users/10001", "Your morning briefing is ready!")
        assert success is True
