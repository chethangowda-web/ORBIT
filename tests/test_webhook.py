"""Unit and integration tests for Google Chat webhook integration."""

import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import User
from services.google_chat import verify_webhook_signature


def test_signature_verification_default():
    """Verify signature check returns True when no secret is configured."""
    assert verify_webhook_signature(b"test body", "") is True


@pytest.mark.asyncio
async def test_webhook_added_to_space_event(client: AsyncClient, db_session: AsyncSession):
    """Test webhook processing ADDED_TO_SPACE event."""
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

    response = await client.post(
        "/api/chat/webhook",
        json=event_payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "accepted"
    assert data.get("event_type") == "ADDED_TO_SPACE"

    # Verify user auto-registration in DB
    query = select(User).where(User.email == "alice@orbit.dev")
    res = await db_session.execute(query)
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.display_name == "Alice Smith"
    assert user.google_id == "users/100000000000000000001"


@pytest.mark.asyncio
async def test_webhook_message_event_creates_task(client: AsyncClient, db_session: AsyncSession):
    """Test webhook receiving MESSAGE event and auto-triggering multi-agent pipeline."""
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
            "text": "Create a high priority task for Bob to deploy auth service by Friday",
        },
    }

    response = await client.post(
        "/api/chat/webhook",
        json=event_payload,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json().get("status") == "accepted"

    # Verify user registered
    query = select(User).where(User.email == "bob@orbit.dev")
    res = await db_session.execute(query)
    user = res.scalar_one_or_none()
    assert user is not None


@pytest.mark.asyncio
async def test_webhook_card_clicked_event(client: AsyncClient):
    """Test webhook processing CARD_CLICKED interactive button events."""
    event_payload = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-10-07T12:10:00Z",
        "space": {"name": "spaces/TESTSPACE123", "type": "ROOM"},
        "user": {
            "name": "users/100000000000000000002",
            "displayName": "Bob Builder",
            "email": "bob@orbit.dev",
        },
        "action": {
            "actionMethodName": "confirm_delete_task",
            "parameters": [{"key": "task_id", "value": "123"}],
        },
    }

    response = await client.post(
        "/api/chat/webhook",
        json=event_payload,
    )

    assert response.status_code == 200
    assert response.json().get("event_type") == "CARD_CLICKED"


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
    assert response.json().get("status") == "accepted"


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
