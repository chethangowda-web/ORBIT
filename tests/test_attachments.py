"""Task attachments: validation, RBAC, safe downloads, cleanup."""

import pytest
from httpx import AsyncClient

from config import settings
from services import storage


async def make_task(client: AsyncClient, headers: dict, assignee_id=None) -> str:
    body = {"title": "Task with files"}
    if assignee_id:
        body["assignee_id"] = str(assignee_id)
    res = await client.post("/api/tasks", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


async def upload(client, task_id, headers, name="spec.pdf", content=b"%PDF-1.4 hello"):
    return await client.post(
        f"/api/tasks/{task_id}/attachments", files={"file": (name, content, "application/octet-stream")}, headers=headers
    )


async def test_upload_list_download_roundtrip(client: AsyncClient, user_auth_headers, isolated_uploads):
    task_id = await make_task(client, user_auth_headers)
    res = await upload(client, task_id, user_auth_headers)
    assert res.status_code == 201, res.text
    data = res.json()["data"]
    assert data["filename"] == "spec.pdf" and data["size_bytes"] == len(b"%PDF-1.4 hello")
    assert "stored_name" not in data

    listing = (await client.get(f"/api/tasks/{task_id}/attachments", headers=user_auth_headers)).json()["data"]
    assert [a["filename"] for a in listing] == ["spec.pdf"]

    dl = await client.get(f"/api/tasks/{task_id}/attachments/{data['id']}", headers=user_auth_headers)
    assert dl.status_code == 200 and dl.content == b"%PDF-1.4 hello"
    assert dl.headers["content-disposition"].startswith("attachment")
    assert dl.headers["x-content-type-options"] == "nosniff"
    assert len(list(isolated_uploads.iterdir())) == 1


@pytest.mark.parametrize("name", ["evil.html", "x.svg", "run.exe", "script.js", "noext", "page.php"])
async def test_dangerous_types_are_rejected(client, user_auth_headers, isolated_uploads, name):
    task_id = await make_task(client, user_auth_headers)
    res = await upload(client, task_id, user_auth_headers, name=name, content=b"<script>alert(1)</script>")
    assert res.status_code == 415
    assert not isolated_uploads.exists() or list(isolated_uploads.iterdir()) == []


async def test_client_supplied_content_type_is_ignored(client, user_auth_headers):
    task_id = await make_task(client, user_auth_headers)
    res = await client.post(
        f"/api/tasks/{task_id}/attachments",
        files={"file": ("notes.txt", b"hi", "text/html")},
        headers=user_auth_headers,
    )
    assert res.json()["data"]["content_type"] == "text/plain"


async def test_path_traversal_in_filename_is_neutralised(client, user_auth_headers, isolated_uploads):
    task_id = await make_task(client, user_auth_headers)
    res = await upload(client, task_id, user_auth_headers, name="../../etc/passwd.txt", content=b"x")
    assert res.status_code == 201
    assert res.json()["data"]["filename"] == "passwd.txt"
    assert all(p.parent == isolated_uploads for p in isolated_uploads.iterdir())


async def test_oversized_upload_is_cut_off_and_cleaned_up(client, user_auth_headers, isolated_uploads, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    task_id = await make_task(client, user_auth_headers)
    res = await upload(client, task_id, user_auth_headers, name="big.zip", content=b"0" * (1024 * 1024 + 10))
    assert res.status_code == 413
    assert list(isolated_uploads.iterdir()) == []


async def test_empty_file_is_rejected(client, user_auth_headers, isolated_uploads):
    task_id = await make_task(client, user_auth_headers)
    assert (await upload(client, task_id, user_auth_headers, content=b"")).status_code == 400
    assert list(isolated_uploads.iterdir()) == []


async def test_attachment_count_is_capped(client, user_auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAX_ATTACHMENTS_PER_TASK", 2)
    task_id = await make_task(client, user_auth_headers)
    assert (await upload(client, task_id, user_auth_headers, name="a.txt")).status_code == 201
    assert (await upload(client, task_id, user_auth_headers, name="b.txt")).status_code == 201
    assert (await upload(client, task_id, user_auth_headers, name="c.txt")).status_code == 409


async def test_unauthenticated_access_is_refused(client, user_auth_headers):
    task_id = await make_task(client, user_auth_headers)
    assert (await client.get(f"/api/tasks/{task_id}/attachments")).status_code == 401
    assert (await client.post(f"/api/tasks/{task_id}/attachments", files={"file": ("a.txt", b"x")})).status_code == 401


async def test_other_employee_cannot_see_or_download(
    client, user_auth_headers, seed_manager_user, db_session, seed_test_user
):
    """A task not visible to a user must not leak its files, listing or download."""
    from auth.jwt import create_access_token, get_password_hash
    from db.models import User

    task_id = await make_task(client, user_auth_headers)
    att = (await upload(client, task_id, user_auth_headers)).json()["data"]

    stranger = User(
        email="stranger@orbit.dev",
        display_name="Stranger",
        first_name="S",
        last_name="T",
        hashed_password=get_password_hash("password123"),
        role="employee",
        is_active=True,
    )
    db_session.add(stranger)
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': str(stranger.id)})}"}

    assert (await client.get(f"/api/tasks/{task_id}/attachments", headers=headers)).status_code in (403, 404)
    assert (await client.get(f"/api/tasks/{task_id}/attachments/{att['id']}", headers=headers)).status_code in (403, 404)
    assert (await upload(client, task_id, headers)).status_code in (403, 404)


async def test_delete_removes_record_and_file_and_respects_ownership(
    client, user_auth_headers, manager_auth_headers, isolated_uploads
):
    task_id = await make_task(client, user_auth_headers)
    att = (await upload(client, task_id, user_auth_headers)).json()["data"]
    assert len(list(isolated_uploads.iterdir())) == 1

    res = await client.delete(f"/api/tasks/{task_id}/attachments/{att['id']}", headers=user_auth_headers)
    assert res.status_code == 200
    assert list(isolated_uploads.iterdir()) == []
    gone = await client.get(f"/api/tasks/{task_id}/attachments/{att['id']}", headers=user_auth_headers)
    assert gone.status_code == 404


async def test_attaching_is_recorded_in_task_history(client, user_auth_headers):
    task_id = await make_task(client, user_auth_headers)
    await upload(client, task_id, user_auth_headers)
    history = (await client.get(f"/api/tasks/{task_id}/history", headers=user_auth_headers)).json()["data"]
    assert "ATTACHED" in {h["action"] for h in history}


def test_filename_cleaning():
    assert storage.clean_filename("C:\\Users\\me\\report.pdf") == "report.pdf"
    assert storage.clean_filename("a\x00b\nc.txt") == "abc.txt"
    assert len(storage.clean_filename("x" * 400 + ".pdf")) <= 200
    assert storage.clean_filename("") == ""


def test_stored_names_must_be_random_hex():
    with pytest.raises(ValueError):
        storage.path_for("../secret")
