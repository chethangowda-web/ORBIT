"""Task comments: access rules, validation, notifications, deletion."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from db.models import NotificationLog, Task, User


async def make_task(db, creator: User, assignee: User | None = None, title="Discuss me") -> Task:
    task = Task(title=title, created_by_id=creator.id, assignee_id=(assignee or creator).id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def test_owner_can_comment_and_list_in_order(client: AsyncClient, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user)
    for text in ("first", "  second  "):
        res = await client.post(f"/api/tasks/{task.id}/comments", json={"body": text}, headers=user_auth_headers)
        assert res.status_code == 201

    listed = (await client.get(f"/api/tasks/{task.id}/comments", headers=user_auth_headers)).json()["data"]
    assert [c["body"] for c in listed] == ["first", "second"]  # oldest first, trimmed
    assert listed[0]["author"]["display_name"] == "Test Employee"
    assert "google_id" not in listed[0]["author"]


async def test_blank_and_oversized_comments_rejected(client: AsyncClient, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user)
    for body in ("", "   ", "x" * 2001):
        res = await client.post(f"/api/tasks/{task.id}/comments", json={"body": body}, headers=user_auth_headers)
        assert res.status_code == 422, body


async def test_employee_cannot_read_or_write_comments_on_tasks_they_cannot_see(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers
):
    foreign = await make_task(db_session, seed_manager_user, title="Private")
    assert (await client.get(f"/api/tasks/{foreign.id}/comments", headers=user_auth_headers)).status_code == 403
    assert (await client.post(f"/api/tasks/{foreign.id}/comments", json={"body": "hi"}, headers=user_auth_headers)).status_code == 403


async def test_commenting_on_a_missing_task_is_404(client: AsyncClient, seed_manager_user, manager_auth_headers):
    res = await client.post(
        "/api/tasks/00000000-0000-0000-0000-000000000000/comments", json={"body": "hi"}, headers=manager_auth_headers
    )
    assert res.status_code == 404


async def test_comment_appears_in_the_audit_trail(client: AsyncClient, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user)
    await client.post(f"/api/tasks/{task.id}/comments", json={"body": "Looks good to me"}, headers=user_auth_headers)
    history = (await client.get(f"/api/tasks/{task.id}/history", headers=user_auth_headers)).json()["data"]
    commented = [h for h in history if h["action"] == "COMMENTED"]
    assert len(commented) == 1
    assert commented[0]["changes"]["comment"]["new"] == "Looks good to me"


async def test_assignee_is_notified_and_author_is_not(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, manager_auth_headers
):
    seed_test_user.google_id = "users/555"
    seed_test_user.google_space_id = "spaces/EMP_DM"
    seed_manager_user.google_space_id = "spaces/MGR_DM"
    await db_session.commit()
    task = await make_task(db_session, seed_manager_user, assignee=seed_test_user)

    with patch("services.notifications.send_dm", new_callable=AsyncMock, return_value=True) as dm, \
         patch("services.notifications.send_text_message", new_callable=AsyncMock, return_value=True) as text:
        res = await client.post(f"/api/tasks/{task.id}/comments", json={"body": "Please add tests"}, headers=manager_auth_headers)
    assert res.status_code == 201

    dm.assert_awaited_once()
    assert "Please add tests" in dm.await_args.args[1]
    text.assert_not_awaited()  # the manager (author, also creator) is not told about their own comment

    logs = (await db_session.execute(select(NotificationLog).where(NotificationLog.type == "task_commented"))).scalars().all()
    assert [log.user_id for log in logs] == [seed_test_user.id]
    assert logs[0].status == "sent"


async def test_commenting_on_your_own_task_notifies_nobody(client: AsyncClient, db_session, seed_test_user, user_auth_headers):
    task = await make_task(db_session, seed_test_user)
    with patch("services.notifications.send_dm", new_callable=AsyncMock) as dm:
        await client.post(f"/api/tasks/{task.id}/comments", json={"body": "note to self"}, headers=user_auth_headers)
    dm.assert_not_awaited()


async def test_notification_failure_never_blocks_the_comment(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, manager_auth_headers
):
    seed_test_user.google_space_id = "spaces/EMP_DM"
    await db_session.commit()
    task = await make_task(db_session, seed_manager_user, assignee=seed_test_user)

    with patch("services.notifications.send_text_message", new_callable=AsyncMock, return_value=False):
        res = await client.post(f"/api/tasks/{task.id}/comments", json={"body": "ping"}, headers=manager_auth_headers)
    assert res.status_code == 201
    log = (await db_session.execute(select(NotificationLog).where(NotificationLog.type == "task_commented"))).scalars().one()
    assert log.status == "failed"


async def test_delete_rules(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers, manager_auth_headers
):
    task = await make_task(db_session, seed_manager_user, assignee=seed_test_user)
    mine = (await client.post(f"/api/tasks/{task.id}/comments", json={"body": "mine"}, headers=user_auth_headers)).json()["data"]["id"]
    theirs = (await client.post(f"/api/tasks/{task.id}/comments", json={"body": "theirs"}, headers=manager_auth_headers)).json()["data"]["id"]

    assert (await client.delete(f"/api/tasks/{task.id}/comments/{theirs}", headers=user_auth_headers)).status_code == 403
    assert (await client.delete(f"/api/tasks/{task.id}/comments/{mine}", headers=user_auth_headers)).status_code == 200
    assert (await client.delete(f"/api/tasks/{task.id}/comments/{theirs}", headers=manager_auth_headers)).status_code == 200
    assert (await client.get(f"/api/tasks/{task.id}/comments", headers=manager_auth_headers)).json()["data"] == []


async def test_manager_can_delete_any_comment_and_wrong_task_is_404(
    client: AsyncClient, db_session, seed_test_user, seed_manager_user, user_auth_headers, manager_auth_headers
):
    task_a = await make_task(db_session, seed_test_user, title="A")
    task_b = await make_task(db_session, seed_test_user, title="B")
    cid = (await client.post(f"/api/tasks/{task_a.id}/comments", json={"body": "x"}, headers=user_auth_headers)).json()["data"]["id"]

    wrong = await client.delete(f"/api/tasks/{task_b.id}/comments/{cid}", headers=manager_auth_headers)
    assert wrong.status_code == 404
    assert (await client.delete(f"/api/tasks/{task_a.id}/comments/{cid}", headers=manager_auth_headers)).status_code == 200
