"""User directory, self-service profile and admin management rules."""

from httpx import AsyncClient

from db.models import User


async def test_self_update_cannot_change_privileged_fields(
    client: AsyncClient, seed_test_user: User, user_auth_headers: dict, db_session
):
    response = await client.patch(
        "/api/users/me",
        json={
            "display_name": "Renamed",
            "role": "admin",
            "is_active": False,
            "google_space_id": "spaces/attacker",
        },
        headers=user_auth_headers,
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["display_name"] == "Renamed"
    assert body["role"] == "employee"
    assert body["is_active"] is True
    assert body["google_space_id"] is None


async def test_invalid_timezone_rejected(client: AsyncClient, seed_test_user, user_auth_headers):
    response = await client.patch(
        "/api/users/me", json={"timezone": "Mars/Olympus"}, headers=user_auth_headers
    )
    assert response.status_code == 422


async def test_directory_hides_sensitive_fields(
    client: AsyncClient, seed_test_user, seed_manager_user, user_auth_headers
):
    response = await client.get("/api/users", headers=user_auth_headers)
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 2
    for row in rows:
        assert "google_id" not in row
        assert "google_space_id" not in row
    assert response.json()["meta"]["total"] == 2


async def test_employee_cannot_see_inactive_users(
    client: AsyncClient, seed_test_user, user_auth_headers, db_session
):
    ghost = User(email="ghost@orbit.dev", display_name="Ghost", role="employee", is_active=False)
    db_session.add(ghost)
    await db_session.commit()

    listing = await client.get("/api/users", headers=user_auth_headers)
    assert all(u["email"] != "ghost@orbit.dev" for u in listing.json()["data"])
    detail = await client.get(f"/api/users/{ghost.id}", headers=user_auth_headers)
    assert detail.status_code == 404


async def test_manager_sees_full_user_detail(
    client: AsyncClient, seed_test_user, seed_manager_user, manager_auth_headers
):
    response = await client.get(f"/api/users/{seed_test_user.id}", headers=manager_auth_headers)
    assert response.status_code == 200
    assert "google_id" in response.json()["data"]


async def test_task_payload_does_not_leak_google_ids(
    client: AsyncClient, seed_test_user, user_auth_headers
):
    created = await client.post(
        "/api/tasks", json={"title": "Self task", "assignee_id": str(seed_test_user.id)},
        headers=user_auth_headers,
    )
    assignee = created.json()["data"]["assignee"]
    assert "google_id" not in assignee and "google_space_id" not in assignee


async def test_only_admin_can_change_roles(
    client: AsyncClient, seed_test_user, seed_manager_user, manager_auth_headers
):
    response = await client.patch(
        f"/api/users/{seed_test_user.id}", json={"role": "manager"}, headers=manager_auth_headers
    )
    assert response.status_code == 403


async def test_admin_can_promote_and_deactivate(
    client: AsyncClient, seed_test_user, seed_admin_user, admin_auth_headers
):
    promoted = await client.patch(
        f"/api/users/{seed_test_user.id}", json={"role": "Manager"}, headers=admin_auth_headers
    )
    assert promoted.status_code == 200
    assert promoted.json()["data"]["role"] == "manager"

    deactivated = await client.patch(
        f"/api/users/{seed_test_user.id}", json={"is_active": False}, headers=admin_auth_headers
    )
    assert deactivated.json()["data"]["is_active"] is False


async def test_unknown_role_rejected(client: AsyncClient, seed_test_user, seed_admin_user, admin_auth_headers):
    response = await client.patch(
        f"/api/users/{seed_test_user.id}", json={"role": "superuser"}, headers=admin_auth_headers
    )
    assert response.status_code == 422


async def test_admin_cannot_demote_or_deactivate_self(
    client: AsyncClient, seed_admin_user, admin_auth_headers
):
    demote = await client.patch(
        f"/api/users/{seed_admin_user.id}", json={"role": "employee"}, headers=admin_auth_headers
    )
    assert demote.status_code == 409
    deactivate = await client.patch(
        f"/api/users/{seed_admin_user.id}", json={"is_active": False}, headers=admin_auth_headers
    )
    assert deactivate.status_code == 409


async def test_last_active_admin_is_protected(
    client: AsyncClient, seed_admin_user, admin_auth_headers, db_session
):
    from auth.jwt import create_access_token

    other = User(email="admin2@orbit.dev", display_name="Admin Two", role="admin", is_active=True)
    db_session.add(other)
    await db_session.commit()

    # Demote the second admin: allowed because the caller remains an active admin.
    ok = await client.patch(
        f"/api/users/{other.id}", json={"role": "manager"}, headers=admin_auth_headers
    )
    assert ok.status_code == 200

    # A deactivated admin token cannot act, and the sole remaining admin is protected.
    token = create_access_token({"sub": str(seed_admin_user.id)})
    blocked = await client.patch(
        f"/api/users/{seed_admin_user.id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert blocked.status_code == 409
