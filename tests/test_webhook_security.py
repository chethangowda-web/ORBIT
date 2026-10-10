"""Webhook authentication, idempotency-adjacent safety and PII handling."""

import logging
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from config import settings
from services.google_chat import CHAT_SERVICE_ACCOUNT, verify_google_chat_bearer_token

MESSAGE_EVENT = {
    "type": "MESSAGE",
    "eventTime": "2026-10-10T09:00:00Z",
    "space": {"name": "spaces/S1", "type": "DM"},
    "user": {"name": "users/42", "displayName": "Pat", "email": "pat@orbit.dev"},
    "message": {
        "name": "spaces/S1/messages/M1",
        "text": "help",
        "sender": {"name": "users/42", "displayName": "Pat", "email": "pat@orbit.dev"},
    },
}


async def test_missing_signature_rejected_when_secret_configured(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_WEBHOOK_SECRET", "s3cret-value")
    response = await client.post("/api/chat/webhook", json=MESSAGE_EVENT)
    assert response.status_code == 403


async def test_unknown_card_action_is_not_forwarded_to_agent(client: AsyncClient):
    event = {
        "type": "CARD_CLICKED",
        "eventTime": "2026-10-10T09:01:00Z",
        "space": {"name": "spaces/S1", "type": "DM"},
        "user": {"name": "users/42", "displayName": "Pat", "email": "pat@orbit.dev"},
        "action": {"actionMethodName": "confirm", "parameters": []},
    }
    with patch("api.webhook.process_message") as agent:
        response = await client.post("/api/chat/webhook", json=event)
    assert response.status_code == 200
    agent.assert_not_called()
    assert "no longer available" in response.json()["text"]


async def test_internal_errors_do_not_leak_exception_text(client: AsyncClient):
    with patch("api.webhook.process_message", side_effect=RuntimeError("db password=hunter2")):
        response = await client.post("/api/chat/webhook", json=MESSAGE_EVENT)
    assert response.status_code == 200
    text = response.json()["text"]
    assert "hunter2" not in text and "RuntimeError" not in text
    assert "ref " in text


async def test_raw_payload_is_not_logged_by_default(client: AsyncClient, caplog):
    caplog.set_level(logging.DEBUG, logger="api.webhook")
    await client.post("/api/chat/webhook", json={**MESSAGE_EVENT, "message": {**MESSAGE_EVENT["message"], "name": "spaces/S1/messages/M2", "text": "show my pending tasks"}})
    webhook_logs = " ".join(r.getMessage() for r in caplog.records if r.name == "api.webhook")
    assert webhook_logs  # the handler does log metadata
    assert "pat@orbit.dev" not in webhook_logs
    assert "show my pending tasks" not in webhook_logs


async def test_malformed_event_returns_generic_400(client: AsyncClient):
    response = await client.post(
        "/api/chat/webhook", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid event schema."


async def test_legacy_alias_still_routes(client: AsyncClient):
    response = await client.post("/webhook", json={"type": "ADDED_TO_SPACE", "space": {"name": "spaces/X"}})
    assert response.status_code == 200


def test_bearer_requires_configured_audience(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "")
    with patch("services.google_chat.id_token.verify_oauth2_token") as verify:
        assert verify_google_chat_bearer_token("Bearer abc") is False
        verify.assert_not_called()


@pytest.mark.parametrize(
    "claims,expected",
    [
        ({"iss": CHAT_SERVICE_ACCOUNT}, True),
        ({"iss": "https://accounts.google.com", "email": CHAT_SERVICE_ACCOUNT, "email_verified": True}, True),
        ({"iss": "https://accounts.google.com", "email": "attacker@gmail.com", "email_verified": True}, False),
        ({"iss": "https://accounts.google.com", "email": CHAT_SERVICE_ACCOUNT, "email_verified": False}, False),
        ({"iss": "https://accounts.google.com"}, False),
    ],
)
def test_bearer_identity_checks(monkeypatch, claims, expected):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")
    with patch("services.google_chat.id_token.verify_oauth2_token", return_value=claims):
        assert verify_google_chat_bearer_token("Bearer abc") is expected


def test_bearer_falls_back_to_chat_certificates(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")
    with patch("services.google_chat.id_token.verify_oauth2_token", side_effect=ValueError("wrong signer")), \
         patch("services.google_chat.id_token.verify_token", return_value={"iss": CHAT_SERVICE_ACCOUNT}) as chat_verify:
        assert verify_google_chat_bearer_token("Bearer abc") is True
    assert chat_verify.call_args.kwargs["certs_url"].endswith(CHAT_SERVICE_ACCOUNT)
