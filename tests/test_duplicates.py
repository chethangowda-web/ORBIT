"""Duplicate-task detection: what counts as 'the same task', in the API, in Chat and for the AI agent."""

import pytest
from httpx import AsyncClient

from services.duplicates import SAME, SIMILAR, find_similar, similarity


# --- the similarity measure ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "a,b",
    [
        ("Send the revised contract to Acme", "Send revised contract to Acme"),
        ("Book the venue for the team offsite", "book venue for team offsite!"),
        ("Fix login bug", "fix the login bug"),
        ("Prepare Q3 deck", "Prepare the Q3 deck"),
    ],
)
def test_the_same_task_worded_slightly_differently_is_the_same(a, b):
    assert similarity(a, b) >= SAME


@pytest.mark.parametrize(
    "a,b",
    [
        ("Review the contract", "Send the contract"),
        ("Plan the offsite", "Book the venue"),
        ("Fix login bug", "Fix billing bug"),
        ("Call the vendor", "Email the vendor"),
        ("Q3 budget", "Q4 budget"),
    ],
)
def test_different_tasks_that_share_a_word_or_two_are_not_flagged(a, b):
    assert similarity(a, b) < SIMILAR


def test_a_task_that_contains_another_is_similar_but_not_the_same():
    score = similarity("Update the website", "Update the website copy and images")
    assert SIMILAR <= score < SAME


def test_empty_or_meaningless_titles_never_match():
    assert similarity("", "Send the invoice") == 0.0
    assert similarity("the a to", "the a to") == 0.0  # nothing but filler words


def test_find_similar_ranks_best_first_and_ignores_weak_matches():
    pool = [
        {"id": 1, "title": "Send revised contract to Acme"},
        {"id": 2, "title": "Send the invoice to Acme"},
        {"id": 3, "title": "Plan the offsite"},
        {"id": 4, "title": "Send the revised contract to Acme today"},
    ]
    found = find_similar("Send the revised contract to Acme", pool)
    assert [item["id"] for _, item in found] == [1, 4]
    assert found[0][0] >= found[1][0]
    assert find_similar("Order lunch", pool) == []


# --- the API ---------------------------------------------------------------------------------------------


async def make(client: AsyncClient, headers: dict, title: str, **extra) -> dict:
    res = await client.post("/api/tasks", json={"title": title, **extra}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["data"]


async def test_the_api_lists_similar_open_tasks_before_you_create(client, manager_auth_headers):
    await make(client, manager_auth_headers, "Send revised contract to Acme")
    done = await make(client, manager_auth_headers, "Send contract to Acme, signed copy")
    await client.post(f"/api/tasks/{done['id']}/complete", headers=manager_auth_headers)

    res = await client.get("/api/tasks/similar", params={"title": "Send the revised contract to Acme"}, headers=manager_auth_headers)
    assert res.status_code == 200
    items = res.json()["data"]
    assert [i["title"] for i in items] == ["Send revised contract to Acme"], "finished tasks are not duplicates"
    assert items[0]["same"] is True and 0 < items[0]["score"] <= 1


async def test_similar_search_only_looks_at_tasks_you_may_see(client, manager_auth_headers, user_auth_headers):
    await make(client, manager_auth_headers, "Send revised contract to Acme")  # the employee has no access to it
    res = await client.get("/api/tasks/similar", params={"title": "Send the revised contract to Acme"}, headers=user_auth_headers)
    assert res.json()["data"] == []


async def test_a_too_short_title_matches_nothing(client, manager_auth_headers):
    await make(client, manager_auth_headers, "Ab")
    res = await client.get("/api/tasks/similar", params={"title": "Ab"}, headers=manager_auth_headers)
    assert res.status_code == 200 and res.json()["data"] == []


async def test_creating_through_the_api_is_never_blocked(client, manager_auth_headers):
    await make(client, manager_auth_headers, "Send revised contract to Acme")
    await make(client, manager_auth_headers, "Send revised contract to Acme")  # the API trusts the caller; the form warns first


# --- Chat -------------------------------------------------------------------------------------------------


async def say(client, headers, text, thread="dup") -> dict:
    res = await client.post("/api/chat/query", json={"message": text, "thread_id": thread}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def count_titled(client, headers, fragment: str) -> int:
    res = await client.get("/api/tasks", params={"q": fragment, "page_size": 50}, headers=headers)
    return len(res.json()["data"])


async def test_chat_does_not_add_the_same_task_twice_and_explains(client, manager_auth_headers):
    first = await say(client, manager_auth_headers, "create a task to send the revised contract to Acme")
    assert "Created" in first["response"]

    second = await say(client, manager_auth_headers, "create a task to send the revised contract to Acme")
    assert "already" in second["response"].lower() and "create it anyway" in second["response"].lower()
    assert await count_titled(client, manager_auth_headers, "revised contract") == 1


async def test_saying_create_it_anyway_adds_the_second_one(client, manager_auth_headers):
    await say(client, manager_auth_headers, "create a task to send the revised contract to Acme", thread="anyway")
    await say(client, manager_auth_headers, "create a task to send the revised contract to Acme", thread="anyway")
    done = await say(client, manager_auth_headers, "create it anyway", thread="anyway")
    assert "Created" in done["response"]
    assert await count_titled(client, manager_auth_headers, "revised contract") == 2


async def test_create_it_anyway_does_nothing_when_nothing_was_waiting(client, manager_auth_headers):
    reply = await say(client, manager_auth_headers, "create it anyway", thread="nothing-waiting")
    assert await count_titled(client, manager_auth_headers, "anyway") == 0
    assert "Created" not in reply["response"]


async def test_a_similar_but_not_identical_task_is_created_with_a_heads_up(client, manager_auth_headers):
    await say(client, manager_auth_headers, "create a task to update the website", thread="similar")
    reply = await say(client, manager_auth_headers, "create a task to update the website copy and images", thread="similar")
    assert "Created" in reply["response"]
    assert "similar task" in reply["response"].lower()
    assert await count_titled(client, manager_auth_headers, "website") == 2
