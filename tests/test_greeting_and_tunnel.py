"""Greeting replies and the dev tunnel script helpers."""

import pytest
from httpx import AsyncClient

from agents.intents import Intent
from scripts.dev_tunnel import endpoint_for, extract_tunnel_url
from services.llm import fallback_intent_classifier


@pytest.mark.parametrize("text", ["hi", "hii", "hello", "Hello ORBIT!", "hey there", "good morning", "Good evening!", "thanks", "thank you", "hi hi"])
def test_pure_greetings_are_greetings(text):
    assert fallback_intent_classifier(text).intent == Intent.GREETING


@pytest.mark.parametrize(
    "text,expected",
    [
        ("hi, show my tasks", Intent.GET_MY_TASKS),
        ("hello can you plan my day", Intent.PLAN_DAY),
        ("thanks, now create a task to deploy the app", Intent.CREATE_TASK),
        ("good morning what are my overdue tasks", Intent.GET_OVERDUE_TASKS),
    ],
)
def test_a_greeting_never_swallows_a_real_request(text, expected):
    assert fallback_intent_classifier(text).intent == expected


async def test_chat_replies_warmly_to_hello(client: AsyncClient, seed_test_user):
    event = {
        "type": "MESSAGE",
        "space": {"name": "spaces/G1", "type": "DM"},
        "user": {"name": "users/77", "displayName": "Tester", "email": seed_test_user.email},
        "message": {"name": "spaces/G1/messages/g1", "text": "hii"},
    }
    reply = (await client.post("/api/chat/webhook", json=event)).json()["text"]
    assert reply.startswith("👋 Hi") and "I didn't quite catch" not in reply


async def test_thanks_gets_a_short_reply(client: AsyncClient, seed_test_user, user_auth_headers):
    res = await client.post("/api/chat/query", json={"message": "thanks!"}, headers=user_auth_headers)
    data = res.json()["data"]
    assert data["metadata"]["intent"] == "GREETING"
    assert "welcome" in data["response"].lower()


def test_tunnel_url_is_parsed_from_cloudflared_output():
    line = "2026-10-10T12:00:00Z INF |  https://corporation-superior-mississippi.trycloudflare.com  |"
    assert extract_tunnel_url(line) == "https://corporation-superior-mississippi.trycloudflare.com"
    assert extract_tunnel_url("INF Starting tunnel connection") is None
    assert extract_tunnel_url("https://example.com/not-a-tunnel") is None


def test_endpoint_url_is_the_webhook_path():
    assert endpoint_for("https://abc.trycloudflare.com/") == "https://abc.trycloudflare.com/api/chat/webhook"
