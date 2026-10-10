"""The system keeps answering when the LLM is slow, failing, or out of quota."""

import asyncio
import time

import pytest

from agents import orchestrator
from config import settings
from services import llm


class FakeCompletion:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    async def __call__(self, **kwargs):
        self.calls += 1
        return await self.behaviour(self.calls, kwargs)


@pytest.fixture
def llm_online(monkeypatch):
    """Pretend an API key exists and give each test a fresh breaker with fast timings."""
    monkeypatch.setattr(settings, "GOOGLE_GEMINI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(settings, "LLM_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(settings, "LLM_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "LLM_BREAKER_FAILURES", 3)
    monkeypatch.setattr(settings, "LLM_BREAKER_COOLDOWN_SECONDS", 60.0)
    monkeypatch.setattr(llm, "llm_breaker", llm.LLMCircuitBreaker())

    async def no_sleep(_):
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)


def install(monkeypatch, behaviour) -> FakeCompletion:
    fake = FakeCompletion(behaviour)
    monkeypatch.setattr(llm.litellm, "acompletion", fake)
    return fake


def reply(text):
    class Msg:
        content = text

    class Choice:
        message = Msg()

    class Resp:
        choices = [Choice()]

    return Resp()


async def test_working_provider_returns_content(llm_online, monkeypatch):
    async def ok(_n, _kw):
        return reply("hello")

    install(monkeypatch, ok)
    assert await llm.call_llm([{"role": "user", "content": "hi"}]) == "hello"


async def test_hung_provider_is_cut_off_by_the_timeout(llm_online, monkeypatch):
    async def hang(_n, _kw):
        await asyncio.sleep(30)

    install(monkeypatch, hang)
    started = time.perf_counter()
    result = await llm.call_llm([{"role": "user", "content": "hi"}], retries=1)
    assert result is None
    assert time.perf_counter() - started < 2  # bounded by LLM_TIMEOUT_SECONDS, not by the provider


async def test_breaker_opens_after_repeated_failures_and_stops_calling(llm_online, monkeypatch):
    async def boom(_n, _kw):
        raise RuntimeError("429 quota exhausted")

    fake = install(monkeypatch, boom)
    messages = [{"role": "user", "content": "hi"}]
    assert await llm.call_llm(messages) is None  # 2 attempts
    assert await llm.call_llm(messages) is None  # 3rd failure opens the breaker
    calls_when_open = fake.calls
    for _ in range(5):
        assert await llm.call_llm(messages) is None
    assert fake.calls == calls_when_open, "an open breaker must not touch the provider"


async def test_breaker_probes_again_after_cooldown_and_recovers(llm_online, monkeypatch):
    state = {"healthy": False}

    async def flaky(_n, _kw):
        if not state["healthy"]:
            raise RuntimeError("down")
        return reply("back")

    install(monkeypatch, flaky)
    messages = [{"role": "user", "content": "hi"}]
    await llm.call_llm(messages)
    await llm.call_llm(messages)
    assert llm.llm_breaker.opened_at is not None

    state["healthy"] = True
    llm.llm_breaker.opened_at -= settings.LLM_BREAKER_COOLDOWN_SECONDS + 1  # cooldown elapsed
    assert await llm.call_llm(messages) == "back"
    assert llm.llm_breaker.opened_at is None and llm.llm_breaker.failures == 0


async def test_one_failure_then_success_does_not_trip_the_breaker(llm_online, monkeypatch):
    async def once_bad(n, _kw):
        if n == 1:
            raise RuntimeError("blip")
        return reply("ok")

    install(monkeypatch, once_bad)
    assert await llm.call_llm([{"role": "user", "content": "hi"}]) == "ok"
    assert llm.llm_breaker.opened_at is None


async def test_chat_still_answers_while_the_llm_is_down(client, llm_online, monkeypatch, seed_test_user, user_auth_headers):
    """With the provider failing, the rule-based classifier keeps the assistant useful."""

    async def boom(_n, _kw):
        raise RuntimeError("provider down")

    install(monkeypatch, boom)
    res = await client.post("/api/chat/query", json={"message": "show my tasks"}, headers=user_auth_headers)
    assert res.status_code == 200
    assert res.json()["data"]["metadata"]["intent"] == "GET_MY_TASKS"


async def test_agent_deadline_returns_a_friendly_message(monkeypatch):
    class SlowGraph:
        async def astream(self, *_a, **_kw):
            await asyncio.sleep(30)
            yield {}

    monkeypatch.setattr(orchestrator, "get_compiled_graph", lambda: SlowGraph())
    monkeypatch.setattr(settings, "AGENT_TIMEOUT_SECONDS", 0.1)
    state = await orchestrator.process_message(user_id="u", space_id="s", message="hello")
    assert state["error_code"] == "AGENT_TIMEOUT"
    assert "try again" in state["response"].lower()


def test_agent_deadline_is_shorter_than_googles_chat_limit():
    assert settings.AGENT_TIMEOUT_SECONDS < 30
