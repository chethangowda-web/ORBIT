"""Notification delivery log endpoint and health endpoint hygiene."""

from httpx import AsyncClient

from db.models import NotificationLog


async def _log(db, user, status="sent", type_="task_assigned", message="hello"):
    db.add(NotificationLog(user_id=user.id, type=type_, status=status, message=message,
                           error_msg="boom" if status == "failed" else None))
    await db.commit()


async def test_employees_cannot_read_notification_log(client: AsyncClient, seed_test_user, user_auth_headers):
    response = await client.get("/api/admin/notifications", headers=user_auth_headers)
    assert response.status_code == 403


async def test_manager_lists_notifications_newest_first_with_names(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, manager_auth_headers
):
    await _log(db_session, seed_test_user, message="first")
    await _log(db_session, seed_test_user, status="failed", message="second")

    response = await client.get("/api/admin/notifications", headers=manager_auth_headers)
    body = response.json()
    assert body["meta"]["total"] == 2
    assert [n["message"] for n in body["data"]] == ["second", "first"]
    assert body["data"][0]["user_name"] == "Test Employee"
    assert body["data"][0]["error_msg"] == "boom"


async def test_notification_filters_and_validation(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, manager_auth_headers
):
    await _log(db_session, seed_test_user, status="sent")
    await _log(db_session, seed_test_user, status="failed", type_="daily_briefing")

    failed = await client.get("/api/admin/notifications?status=failed", headers=manager_auth_headers)
    assert [n["status"] for n in failed.json()["data"]] == ["failed"]
    by_type = await client.get("/api/admin/notifications?type=daily_briefing", headers=manager_auth_headers)
    assert by_type.json()["meta"]["total"] == 1
    bad = await client.get("/api/admin/notifications?status=bogus", headers=manager_auth_headers)
    assert bad.status_code == 422


async def test_health_never_exposes_exception_text(client: AsyncClient, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    async def boom(self, *args, **kwargs):
        raise RuntimeError("password authentication failed for user orbit at 10.0.0.5")

    monkeypatch.setattr(AsyncSession, "execute", boom)
    response = await client.get("/api/health")
    text = response.text
    assert "10.0.0.5" not in text and "password" not in text
    assert response.json()["data"]["database"] == "disconnected"
