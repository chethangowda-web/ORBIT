"""The agent workflow is recorded step by step and visible to the user; integrations report their status."""

from httpx import AsyncClient

from db.models import Task, User


async def ask(client: AsyncClient, headers: dict, message: str, thread: str = "wf") -> dict:
    res = await client.post("/api/chat/query", json={"message": message, "thread_id": thread}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def test_each_reply_carries_an_ordered_workflow(client, db_session, seed_manager_user, manager_auth_headers):
    db_session.add(Task(title="Prepare deck", priority="HIGH", status="TODO", created_by_id=seed_manager_user.id))
    await db_session.commit()

    data = await ask(client, manager_auth_headers, "what should I focus on today?")
    meta = data["metadata"]
    steps = meta["steps"]

    assert [s["node"] for s in steps][0] == "supervisor", "the supervisor always runs first"
    assert steps[1]["node"] == "planner_agent"
    supervisor = steps[0]
    assert supervisor["intent"] == "PLAN_DAY"
    assert supervisor["classifier"] == "rules"  # tests run offline: the LLM key is blanked
    assert supervisor["confidence"] is not None
    # tools are attributed to the agent that called them, in order
    assert steps[1]["tools"] == meta["tool_calls_made"] and len(steps[1]["tools"]) >= 1
    assert all(s["duration_ms"] >= 0 for s in steps)
    assert meta["classifier"] == "rules"


async def test_steps_are_stored_with_the_run_and_listed_back(client, seed_test_user, user_auth_headers):
    await ask(client, user_auth_headers, "show my tasks", thread="wf-stored")
    res = await client.get("/api/chat/traces", params={"limit": 5}, headers=user_auth_headers)
    run = res.json()["data"]["items"][0]
    assert run["intent"] == "GET_MY_TASKS"
    assert run["classifier"] == "rules"
    assert [s["node"] for s in run["steps"]][:2] == ["supervisor", "task_agent"]


async def test_confirmation_turns_are_labelled_as_a_flow_not_a_classification(
    client, db_session, seed_manager_user, manager_auth_headers
):
    db_session.add(Task(title="Old draft", priority="LOW", status="TODO", created_by_id=seed_manager_user.id))
    await db_session.commit()
    await ask(client, manager_auth_headers, "delete the old draft", thread="wf-confirm")
    confirm = await ask(client, manager_auth_headers, "yes", thread="wf-confirm")
    assert confirm["metadata"]["steps"][0]["classifier"] == "flow"


async def test_trace_total_counts_all_of_a_users_runs(client, seed_test_user, user_auth_headers):
    for i in range(3):
        await ask(client, user_auth_headers, "help", thread=f"wf-count-{i}")
    res = await client.get("/api/chat/traces", params={"limit": 1}, headers=user_auth_headers)
    data = res.json()["data"]
    assert len(data["items"]) == 1 and data["total"] == 3


# --- integrations ---------------------------------------------------------------------------------


async def test_integrations_status_is_for_managers_only(client, user_auth_headers, manager_auth_headers):
    assert (await client.get("/api/admin/integrations", headers=user_auth_headers)).status_code == 403
    assert (await client.get("/api/admin/integrations", headers=manager_auth_headers)).status_code == 200


async def test_integrations_report_chat_activity_without_leaking_secrets(
    client, db_session, manager_auth_headers, seed_test_user
):
    event = {
        "type": "MESSAGE",
        "space": {"name": "spaces/I1", "type": "DM"},
        "user": {"name": "users/555", "displayName": "Tester", "email": seed_test_user.email},
        "message": {"name": "spaces/I1/messages/i1", "text": "hi"},
    }
    assert (await client.post("/api/chat/webhook", json=event)).status_code == 200

    data = (await client.get("/api/admin/integrations", headers=manager_auth_headers)).json()["data"]
    chat = data["google_chat"]
    assert chat["events_24h"] >= 1 and chat["last_event_at"] is not None
    assert chat["linked_users"] >= 1
    assert set(chat) >= {"verification_enabled", "audience_configured", "service_account_configured", "deliveries_24h"}
    assert data["llm"]["model"] and "circuit_open" in data["llm"]
    assert set(data["email"]) >= {"enabled", "deliveries_24h"}
    text = str(data).lower()
    assert "password" not in text and "private_key" not in text and "api_key" not in text
