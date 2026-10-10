"""Prometheus endpoint: opt-in, optionally token-protected, low-cardinality labels."""

from httpx import AsyncClient

from config import settings


async def test_metrics_are_disabled_by_default(client: AsyncClient):
    assert (await client.get("/metrics")).status_code == 404


async def test_metrics_exposed_when_enabled(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    await client.get("/health")

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "orbit_http_requests_total" in response.text
    assert 'path="/health"' in response.text


async def test_metrics_token_is_enforced(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "scrape-secret")

    assert (await client.get("/metrics")).status_code == 401
    assert (await client.get("/metrics", headers={"Authorization": "Bearer nope"})).status_code == 401
    ok = await client.get("/metrics", headers={"Authorization": "Bearer scrape-secret"})
    assert ok.status_code == 200


async def test_http_labels_use_route_templates_not_raw_ids(
    client: AsyncClient, monkeypatch, seed_manager_user, manager_auth_headers
):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    created = await client.post("/api/tasks", json={"title": "metric task"}, headers=manager_auth_headers)
    task_id = created.json()["data"]["id"]
    await client.get(f"/api/tasks/{task_id}", headers=manager_auth_headers)

    text = (await client.get("/metrics")).text
    assert 'path="/api/tasks/{task_id}"' in text
    assert task_id not in text


async def test_unmatched_paths_share_one_label(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    await client.get("/definitely/not/a/route/12345")
    text = (await client.get("/metrics")).text
    assert 'path="unmatched"' in text
    assert "12345" not in text


async def test_agent_runs_and_tool_calls_are_counted(
    client: AsyncClient, monkeypatch, seed_test_user, user_auth_headers
):
    monkeypatch.setattr(settings, "METRICS_ENABLED", True)
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    await client.post("/api/chat/query", json={"message": "show my pending tasks"}, headers=user_auth_headers)

    text = (await client.get("/metrics")).text
    assert 'orbit_agent_runs_total{intent="GET_MY_TASKS",status="SUCCESS"}' in text
    assert 'orbit_tool_calls_total{tool="get_user_tasks"}' in text
    assert "orbit_agent_run_duration_seconds_count" in text


def test_notification_outcomes_are_counted():
    from metrics import record_notification, render

    record_notification("unit_test_type", "skipped")
    body, content_type = render()
    assert b'orbit_notifications_total{status="skipped",type="unit_test_type"}' in body
    assert content_type.startswith("text/plain")
