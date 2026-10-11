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


ADDON_EMAIL = "service-495048386884@gcp-sa-gsuiteaddons.iam.gserviceaccount.com"


@pytest.mark.parametrize(
    "configured,email,expected",
    [
        ("495048386884", ADDON_EMAIL, True),  # your project's add-on service agent
        ("", ADDON_EMAIL, False),  # not configured: rejected, never guessed
        ("111111111111", ADDON_EMAIL, False),  # another project's add-on agent
        ("495048386884", "service-495048386884@evil.iam.gserviceaccount.com", False),
    ],
)
def test_workspace_addon_identity_requires_matching_project_number(monkeypatch, configured, email, expected):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "https://x.example/api/chat/webhook")
    monkeypatch.setattr(settings, "GOOGLE_CHAT_ADDON_PROJECT_NUMBER", configured)
    claims = {"iss": "https://accounts.google.com", "email": email, "email_verified": True}
    with patch("services.google_chat.id_token.verify_oauth2_token", return_value=claims):
        assert verify_google_chat_bearer_token("Bearer abc") is expected


def test_small_clock_differences_are_tolerated(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")
    with patch("services.google_chat.id_token.verify_oauth2_token", return_value={"iss": CHAT_SERVICE_ACCOUNT}) as verify:
        assert verify_google_chat_bearer_token("Bearer abc") is True
    assert verify.call_args.kwargs["clock_skew_in_seconds"] >= 10


def test_bearer_falls_back_to_chat_certificates(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CHAT_VERIFY_AUTH", True)
    monkeypatch.setattr(settings, "GOOGLE_CHAT_AUDIENCE", "123456789012")
    with patch("services.google_chat.id_token.verify_oauth2_token", side_effect=ValueError("wrong signer")), \
         patch("services.google_chat.id_token.verify_token", return_value={"iss": CHAT_SERVICE_ACCOUNT}) as chat_verify:
        assert verify_google_chat_bearer_token("Bearer abc") is True
    assert chat_verify.call_args.kwargs["certs_url"].endswith(CHAT_SERVICE_ACCOUNT)


async def test_dm_space_is_remembered_for_proactive_messages(client: AsyncClient, db_session):
    from sqlalchemy import select

    from db.models import User

    event = {**MESSAGE_EVENT, "space": {"name": "spaces/DMSPACE9", "type": "DM"}}
    event["message"] = {**MESSAGE_EVENT["message"], "name": "spaces/DMSPACE9/messages/M9"}
    await client.post("/api/chat/webhook", json=event)

    user = (await db_session.execute(select(User).where(User.email == "pat@orbit.dev"))).scalar_one()
    assert user.google_space_id == "spaces/DMSPACE9"


async def test_group_space_is_not_stored_as_dm_space(client: AsyncClient, db_session):
    from sqlalchemy import select

    from db.models import User

    event = {**MESSAGE_EVENT, "space": {"name": "spaces/TEAMROOM", "type": "ROOM"}}
    event["message"] = {**MESSAGE_EVENT["message"], "name": "spaces/TEAMROOM/messages/M5"}
    await client.post("/api/chat/webhook", json=event)

    user = (await db_session.execute(select(User).where(User.email == "pat@orbit.dev"))).scalar_one()
    assert user.google_space_id is None


async def test_send_dm_fails_cleanly_when_dm_space_cannot_be_found():
    from unittest.mock import AsyncMock, MagicMock

    from services.google_chat import send_dm

    not_found = MagicMock()
    not_found.status_code = 404
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=not_found), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        assert await send_dm("users/123", "hi") is False
        post.assert_not_awaited()


async def test_send_dm_uses_known_space_without_lookup():
    from unittest.mock import AsyncMock, MagicMock

    from services.google_chat import send_dm

    ok = MagicMock()
    ok.status_code = 200
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as lookup, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=ok):
        assert await send_dm("users/123", "hi", space_id="spaces/KNOWN") is True
        lookup.assert_not_awaited()
