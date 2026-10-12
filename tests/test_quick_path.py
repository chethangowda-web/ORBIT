"""Simple, unambiguous requests are answered by the instant built-in check; the AI is kept for the rest.

With a free key the AI allows only a handful of requests a day, so spending one on "help" or "show my
tasks" is wasteful and, when a model is slow, adds seconds for no benefit.
"""

import pytest

from agents import supervisor
from agents.intents import Intent


@pytest.fixture
def ai_online(monkeypatch):
    """The AI is available; any call to it is recorded."""
    calls = []

    async def fake_call_llm(*args, **kwargs):
        calls.append(args or kwargs)
        return None  # as if it could not answer: the rules take over

    monkeypatch.setattr(supervisor, "llm_available", lambda: True)
    monkeypatch.setattr(supervisor, "call_llm", fake_call_llm)
    return calls


@pytest.mark.parametrize(
    "text,intent",
    [
        ("help", Intent.HELP),
        ("hi", Intent.GREETING),
        ("show my tasks", Intent.GET_MY_TASKS),
        ("list my tasks", Intent.GET_MY_TASKS),
        ("what are my overdue tasks?", Intent.GET_OVERDUE_TASKS),
    ],
)
async def test_simple_requests_never_use_the_ai(ai_online, text, intent):
    result, source = await supervisor.classify_intent_with_source(text)
    assert result.intent == intent
    assert source == "quick"
    assert ai_online == [], "no AI request was spent"


@pytest.mark.parametrize(
    "text",
    [
        "create a high priority task for John to deploy the frontend by Friday",  # needs entity extraction
        "plan my day",  # the plan itself is written by the AI anyway
        "Move all of John's overdue tasks to Rahul and make them high priority",  # looks like a lookup, is multi-step
        "show all my tasks and then make the first one high priority",
        "who is overloaded?",
    ],
)
async def test_everything_else_still_asks_the_ai(ai_online, text):
    await supervisor.classify_intent_with_source(text)
    assert len(ai_online) == 1


async def test_without_the_ai_the_rules_answer_and_say_so(monkeypatch):
    monkeypatch.setattr(supervisor, "llm_available", lambda: False)
    result, source = await supervisor.classify_intent_with_source("show my tasks")
    assert result.intent == Intent.GET_MY_TASKS and source == "rules"
