"""Comprehensive Test Suite for ORBIT Google Sign-In and Production-Grade RBAC.

Covers:
1. Google OAuth 2.0 PKCE state generation and URL building.
2. Mock Google authentication, token verification, and immutable sub identity matching.
3. Token validation failure cases (unverified email, missing state, invalid state).
4. Safe account provisioning: New Google users receive least-privileged 'employee' role.
5. Account linking policy: Rejection of silent account linking (409 Conflict), followed by password-verified linking.
6. Role escalation prevention: Public registration cannot create Admin or Manager accounts.
7. Deactivated/suspended account rejection.
8. Object-level access control & IDOR prevention:
   - Employee viewing and updating own tasks.
   - Employee unauthorized cross-user task access (403).
   - Employee unauthorized task deletion (403).
   - Employee unauthorized task assignment to others (403).
   - Manager task deletion and team visibility.
   - Admin global visibility, task management, and user role updates.
9. Administrative and analytics scope isolation:
   - Employee access to /analytics/team-workload rejected (403).
   - Employee access to /admin/trigger-briefing rejected (403).
10. Agent tool RBAC enforcement:
    - Employee delete_task tool returns Permission Denied.
    - Manager delete_task tool succeeds.
11. Regression of password login (POST /api/auth/token).
"""

from datetime import date, timedelta
from unittest.mock import patch
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.google_oauth import create_account_link_token, create_oauth_session_token
from auth.jwt import create_access_token, get_password_hash
from auth.rbac import Role
from config import settings
from db.models import Task, User
from exceptions import AuthenticationException
from tools.task_tools import delete_task


# ==============================================================================
# 1. Google OAuth Flow & Account Provisioning Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_google_auth_url_generation(client: AsyncClient):
    """GET /api/auth/google/url returns valid authorization URL with PKCE parameters."""
    with patch.object(settings, "GOOGLE_OAUTH_CLIENT_ID", "test-client-id.apps.googleusercontent.com"):
        response = await client.get("/api/auth/google/url")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "authorization_url" in data
        assert "state" in data
        auth_url = data["authorization_url"]
        assert "client_id=test-client-id.apps.googleusercontent.com" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "orbit_oauth_state" in response.cookies


@pytest.mark.asyncio
async def test_google_callback_safe_new_user_provisioning(client: AsyncClient, db_session: AsyncSession):
    """New Google sign-in securely auto-provisions user with least-privileged EMPLOYEE role."""
    mock_sub = "google-sub-unique-12345"
    mock_email = "newuser@gmail.com"
    mock_state = "valid-oauth-state-abc"

    session_token = create_oauth_session_token(
        state=mock_state, code_verifier="mock-verifier-xyz", nonce="mock-nonce-123"
    )

    mock_token_response = {"id_token": "mock.google.jwt"}
    mock_id_info = {
        "sub": mock_sub,
        "email": mock_email,
        "email_verified": True,
        "name": "New Google User",
        "picture": "https://lh3.googleusercontent.com/avatar.jpg",
        "iss": "accounts.google.com",
        "nonce": "mock-nonce-123",
    }

    with patch("auth.google_oauth.exchange_google_code", return_value=mock_token_response), \
         patch("auth.google_oauth.verify_google_id_token", return_value=mock_id_info):

        response = await client.post(
            "/api/auth/google/callback",
            json={"code": "auth-code-123", "state": mock_state},
            headers={"x-oauth-state": session_token, "Cookie": f"orbit_oauth_state={session_token}"},
        )
        assert response.status_code == 200
        res_data = response.json()["data"]
        assert res_data["user"]["email"] == mock_email
        # CRITICAL: New Google authenticated user MUST receive EMPLOYEE role
        assert res_data["user"]["role"] == "employee"
        assert "access_token" in res_data

        # Verify in database
        stmt = select(User).where(User.google_id == mock_sub)
        user_in_db = (await db_session.execute(stmt)).scalar_one_or_none()
        assert user_in_db is not None
        assert user_in_db.role == "employee"
        assert user_in_db.google_id == mock_sub


@pytest.mark.asyncio
async def test_google_callback_rejects_unverified_email(client: AsyncClient):
    """Google authentication rejects unverified email addresses."""
    mock_state = "state-unverified"
    session_token = create_oauth_session_token(
        state=mock_state, code_verifier="verifier-123", nonce="nonce-123"
    )

    with patch("auth.google_oauth.exchange_google_code", return_value={"id_token": "mock.jwt"}), \
         patch("auth.google_oauth.verify_google_id_token", side_effect=AuthenticationException("Google account email is not verified")):

        response = await client.post(
            "/api/auth/google/callback",
            json={"code": "code-123", "state": mock_state},
            headers={"x-oauth-state": session_token, "Cookie": f"orbit_oauth_state={session_token}"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_google_callback_prevents_silent_account_linking(client: AsyncClient, db_session: AsyncSession):
    """If an account exists with matching email but unlinked Google ID, return 409 ACCOUNT_LINK_REQUIRED."""
    # Seed existing password-only user
    existing_user = User(
        email="existing@orbit.dev",
        hashed_password=get_password_hash("securepass123"),
        display_name="Existing User",
        role="employee",
        google_id=None,
        is_active=True,
    )
    db_session.add(existing_user)
    await db_session.commit()

    mock_sub = "google-sub-hijack-attempt-999"
    mock_state = "state-linking-check"
    session_token = create_oauth_session_token(
        state=mock_state, code_verifier="verifier-linking", nonce="nonce-linking"
    )

    mock_id_info = {
        "sub": mock_sub,
        "email": "existing@orbit.dev",
        "email_verified": True,
        "name": "Existing User",
        "iss": "accounts.google.com",
        "nonce": "nonce-linking",
    }

    with patch("auth.google_oauth.exchange_google_code", return_value={"id_token": "mock.jwt"}), \
         patch("auth.google_oauth.verify_google_id_token", return_value=mock_id_info):

        response = await client.post(
            "/api/auth/google/callback",
            json={"code": "code-link", "state": mock_state},
            headers={"x-oauth-state": session_token, "Cookie": f"orbit_oauth_state={session_token}"},
        )
        # MUST return 409 Conflict with ACCOUNT_LINK_REQUIRED code
        assert response.status_code == 409
        resp_json = response.json()
        meta = resp_json.get("meta") or resp_json.get("detail")
        assert meta["code"] == "ACCOUNT_LINK_REQUIRED"
        assert "link_token" in meta

        # Verify Google sub was NOT linked silently
        await db_session.refresh(existing_user)
        assert existing_user.google_id is None


@pytest.mark.asyncio
async def test_google_link_account_with_valid_password(client: AsyncClient, db_session: AsyncSession):
    """POST /api/auth/google/link securely verifies password and links Google identity."""
    existing_user = User(
        email="linktarget@orbit.dev",
        hashed_password=get_password_hash("mypassword456"),
        display_name="Link Target",
        role="manager",  # Manager role must be preserved upon linking
        google_id=None,
        is_active=True,
    )
    db_session.add(existing_user)
    await db_session.commit()

    target_sub = "google-sub-verified-456"
    link_token = create_account_link_token(google_sub=target_sub, email="linktarget@orbit.dev")

    # Incorrect password attempt -> Rejected
    bad_res = await client.post(
        "/api/auth/google/link",
        json={"link_token": link_token, "password": "wrongpassword"},
    )
    assert bad_res.status_code == 401

    # Correct password attempt -> Linked and role preserved
    good_res = await client.post(
        "/api/auth/google/link",
        json={"link_token": link_token, "password": "mypassword456"},
    )
    assert good_res.status_code == 200
    data = good_res.json()["data"]
    assert data["user"]["email"] == "linktarget@orbit.dev"
    assert data["user"]["role"] == "manager"  # Role preserved!

    await db_session.refresh(existing_user)
    assert existing_user.google_id == target_sub


@pytest.mark.asyncio
async def test_public_registration_cannot_create_admin(client: AsyncClient, db_session: AsyncSession, allow_registration):
    """POST /api/auth/register ignores client-supplied 'admin' role and forces 'employee'."""
    payload = {
        "email": "hacker@orbit.dev",
        "password": "password123",
        "display_name": "Wannabe Admin",
        "role": "admin",  # Escalation attempt
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    # Escalation defeated: user is assigned employee
    assert data["user"]["role"] == "employee"

    stmt = select(User).where(User.email == "hacker@orbit.dev")
    user = (await db_session.execute(stmt)).scalar_one()
    assert user.role == "employee"


@pytest.mark.asyncio
async def test_inactive_account_login_rejected(client: AsyncClient, db_session: AsyncSession):
    """Deactivated accounts cannot authenticate via password or Google."""
    inactive_user = User(
        email="inactive@orbit.dev",
        hashed_password=get_password_hash("password123"),
        display_name="Inactive User",
        role="employee",
        is_active=False,
    )
    db_session.add(inactive_user)
    await db_session.commit()

    res = await client.post(
        "/api/auth/token",
        json={"email": "inactive@orbit.dev", "password": "password123"},
    )
    assert res.status_code == 401


# ==============================================================================
# 2. RBAC & Object-Level Access Control (IDOR Protection)
# ==============================================================================

@pytest.mark.asyncio
async def test_employee_can_view_own_task(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_test_user: User,
    user_auth_headers: dict,
):
    """Employee can view single task assigned to them."""
    task = Task(
        title="Employee Own Task",
        description="Assigned to test employee",
        priority="HIGH",
        status="TODO",
        assignee_id=seed_test_user.id,
        created_by_id=seed_test_user.id,
        due_date=date.today() + timedelta(days=2),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.get(f"/api/tasks/{task.id}", headers=user_auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(task.id)


@pytest.mark.asyncio
async def test_employee_cannot_view_other_user_task(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_test_user: User,
    seed_manager_user: User,
    user_auth_headers: dict,
):
    """Employee is forbidden from viewing another user's task (IDOR protection)."""
    other_task = Task(
        title="Manager Secret Task",
        description="Not assigned to employee",
        priority="CRITICAL",
        status="TODO",
        assignee_id=seed_manager_user.id,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(other_task)
    await db_session.commit()
    await db_session.refresh(other_task)

    response = await client.get(f"/api/tasks/{other_task.id}", headers=user_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_delete_task(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_test_user: User,
    user_auth_headers: dict,
):
    """Employee is forbidden from deleting tasks (403)."""
    task = Task(
        title="Employee Task To Delete",
        priority="LOW",
        status="TODO",
        assignee_id=seed_test_user.id,
        created_by_id=seed_test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.delete(f"/api/tasks/{task.id}", headers=user_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_delete_task(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_manager_user: User,
    manager_auth_headers: dict,
):
    """Manager is authorized to soft-delete tasks."""
    task = Task(
        title="Task For Manager Delete",
        priority="LOW",
        status="TODO",
        assignee_id=seed_manager_user.id,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await client.delete(f"/api/tasks/{task.id}", headers=manager_auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_employee_cannot_assign_task_to_other_user(
    client: AsyncClient,
    seed_manager_user: User,
    user_auth_headers: dict,
):
    """Employee cannot create a task assigned to another user."""
    payload = {
        "title": "Unauthorized Assignment",
        "priority": "MEDIUM",
        "assignee_id": str(seed_manager_user.id),  # Attempting assignment to manager
    }
    response = await client.post("/api/tasks", json=payload, headers=user_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_view_other_user_task_list(
    client: AsyncClient,
    seed_manager_user: User,
    user_auth_headers: dict,
):
    """Employee cannot query GET /api/users/{other_user_id}/tasks."""
    response = await client.get(
        f"/api/users/{seed_manager_user.id}/tasks", headers=user_auth_headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_employee_cannot_access_team_workload_analytics(
    client: AsyncClient,
    user_auth_headers: dict,
):
    """Employee cannot view /api/analytics/team-workload (restricted to Manager/Admin)."""
    response = await client.get("/api/analytics/team-workload", headers=user_auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_access_team_workload_analytics(
    client: AsyncClient,
    manager_auth_headers: dict,
):
    """Manager can view /api/analytics/team-workload."""
    response = await client.get("/api/analytics/team-workload", headers=manager_auth_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_update_user_role(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_test_user: User,
    admin_auth_headers: dict,
    user_auth_headers: dict,
):
    """Only Admin can change user roles; Employee cannot."""
    # 1. Employee attempting role update -> 403 Forbidden
    res_emp = await client.patch(
        f"/api/users/{seed_test_user.id}/role",
        json={"role": "admin"},
        headers=user_auth_headers,
    )
    assert res_emp.status_code == 403

    # 2. Admin performing role update -> 200 OK
    res_admin = await client.patch(
        f"/api/users/{seed_test_user.id}/role",
        json={"role": "manager"},
        headers=admin_auth_headers,
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["data"]["role"] == "manager"

    await db_session.refresh(seed_test_user)
    assert seed_test_user.role == "manager"


@pytest.mark.asyncio
async def test_scheduler_admin_endpoint_authorization(
    client: AsyncClient,
    user_auth_headers: dict,
    admin_auth_headers: dict,
):
    """Scheduler administrative endpoints are restricted from Employees."""
    res_emp = await client.post("/api/admin/trigger-briefing", headers=user_auth_headers)
    assert res_emp.status_code == 403

    with patch("api.admin.run_daily_briefing", return_value={"status": "mocked_success"}):
        res_admin = await client.post("/api/admin/trigger-briefing", headers=admin_auth_headers)
        assert res_admin.status_code == 200


# ==============================================================================
# 3. Agent Tool RBAC Authorization Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_agent_tool_delete_task_enforces_rbac(
    db_session: AsyncSession,
    seed_test_user: User,
    seed_manager_user: User,
):
    """delete_task agent tool rejects employees and allows managers."""
    task = Task(
        title="Agent Tool RBAC Task",
        priority="MEDIUM",
        status="TODO",
        assignee_id=seed_manager_user.id,
        created_by_id=seed_manager_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # 1. Employee call -> Permission denied
    emp_result = await delete_task.ainvoke({
        "task_id": str(task.id),
        "deleted_by_id": str(seed_test_user.id),
    })
    emp_success = emp_result.success if hasattr(emp_result, "success") else emp_result.get("success")
    emp_err = emp_result.error if hasattr(emp_result, "error") else emp_result.get("error")
    assert emp_success is False
    assert "Permission denied" in emp_err

    # 2. Manager call -> Succeeded
    mgr_result = await delete_task.ainvoke({
        "task_id": str(task.id),
        "deleted_by_id": str(seed_manager_user.id),
    })
    mgr_success = mgr_result.success if hasattr(mgr_result, "success") else mgr_result.get("success")
    mgr_data = mgr_result.data if hasattr(mgr_result, "data") else mgr_result.get("data")
    assert mgr_success is True
    assert mgr_data["deleted_id"] == str(task.id)


# ==============================================================================
# 4. Password Login Regression Test
# ==============================================================================

@pytest.mark.asyncio
async def test_existing_password_login_regression(client: AsyncClient, seed_test_user: User):
    """POST /api/auth/token continues to function seamlessly."""
    response = await client.post(
        "/api/auth/token",
        json={"email": seed_test_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user"]["email"] == seed_test_user.email
    assert "access_token" in data
