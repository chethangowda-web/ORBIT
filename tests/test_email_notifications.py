"""Optional email channel: off by default, opt-out respected, never breaks the task change."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from config import settings
from db.models import NotificationLog, UserPreference
from services import email as email_service
from services.email import build_message, is_valid_address, send_email


@pytest.fixture
def smtp_on(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "EMAIL_FROM", "orbit@test.dev")
    sent = []
    monkeypatch.setattr(email_service, "_send_blocking", lambda msg: sent.append(msg))
    return sent


async def email_logs(db_session):
    rows = (await db_session.execute(select(NotificationLog).where(NotificationLog.type.like("email:%")))).scalars().all()
    return list(rows)


def test_email_is_disabled_without_smtp_settings():
    assert not email_service.email_enabled()


async def test_send_skips_when_disabled():
    assert (await send_email("a@b.dev", "s", "t"))[0] == "skipped"


def test_address_validation_rejects_header_injection():
    assert is_valid_address("sarah@orbit.dev")
    assert not is_valid_address("a@b.dev\nBcc: evil@x.dev")
    assert not is_valid_address("not-an-email")
    assert not is_valid_address(None)


def test_subject_cannot_inject_headers(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FROM", "orbit@test.dev")
    msg = build_message("a@b.dev", "Hello\r\nBcc: evil@x.dev", "body")
    assert "\n" not in msg["Subject"] and msg["Bcc"] is None


def test_html_part_escapes_task_content(monkeypatch):
    monkeypatch.setattr(settings, "EMAIL_FROM", "orbit@test.dev")
    msg = build_message("a@b.dev", "s", "<script>alert(1)</script>", link="http://x/tasks/1")
    html_part = msg.get_body(preferencelist=("html",)).get_content()
    assert "<script>" not in html_part and "&lt;script&gt;" in html_part


async def test_smtp_failure_reports_failed_instead_of_raising(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "EMAIL_FROM", "orbit@test.dev")

    def boom(_msg):
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(email_service, "_send_blocking", boom)
    status, error = await send_email("a@b.dev", "s", "t")
    assert status == "failed" and "smtp down" in error


async def test_assigning_a_task_emails_the_assignee(
    client: AsyncClient, db_session, smtp_on, manager_auth_headers, seed_test_user
):
    res = await client.post(
        "/api/tasks",
        json={"title": "Prepare the deck", "assignee_id": str(seed_test_user.id)},
        headers=manager_auth_headers,
    )
    assert res.status_code == 201
    assert len(smtp_on) == 1
    msg = smtp_on[0]
    assert msg["To"] == seed_test_user.email
    assert "Prepare the deck" in msg["Subject"]
    logs = await email_logs(db_session)
    assert [l.status for l in logs] == ["sent"]


async def test_user_can_opt_out_of_email(
    client: AsyncClient, db_session, smtp_on, manager_auth_headers, seed_test_user
):
    db_session.add(UserPreference(user_id=seed_test_user.id, key="email_notifications", value="off"))
    await db_session.commit()
    await client.post(
        "/api/tasks",
        json={"title": "Quiet one", "assignee_id": str(seed_test_user.id)},
        headers=manager_auth_headers,
    )
    assert smtp_on == []
    assert await email_logs(db_session) == []


async def test_email_outage_does_not_break_task_creation(
    client: AsyncClient, db_session, monkeypatch, manager_auth_headers, seed_test_user
):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "EMAIL_FROM", "orbit@test.dev")

    def boom(_msg):
        raise TimeoutError("smtp timeout")

    monkeypatch.setattr(email_service, "_send_blocking", boom)
    res = await client.post(
        "/api/tasks",
        json={"title": "Still created", "assignee_id": str(seed_test_user.id)},
        headers=manager_auth_headers,
    )
    assert res.status_code == 201
    assert [l.status for l in await email_logs(db_session)] == ["failed"]
