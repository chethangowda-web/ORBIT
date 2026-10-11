"""Chat user mapping and the event ledger under awkward but realistic conditions."""

from datetime import timedelta

from sqlalchemy import select

from api.webhook import get_or_create_google_user
from crud import chat_events
from db.base import utc_now
from db.models import ChatEventLedger, User
from schemas.chat import GoogleChatUser


async def make_user(db, email: str, **kw) -> User:
    user = User(email=email, display_name=kw.pop("display_name", "Someone"), role="employee", is_active=True, **kw)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def count_users(db) -> int:
    return len((await db.execute(select(User))).scalars().all())


# --- identity ----------------------------------------------------------------------------------


async def test_chat_email_matches_an_existing_account_regardless_of_case(db_session):
    existing = await make_user(db_session, "alice@corp.com")
    resolved = await get_or_create_google_user(
        db_session, GoogleChatUser(name="users/100", displayName="Alice", email="Alice@Corp.COM")
    )
    assert resolved.id == existing.id
    assert resolved.google_id == "users/100"
    assert await count_users(db_session) == 1, "a second account must not be created for the same person"


async def test_first_event_without_email_then_a_later_event_with_email_does_not_crash(db_session):
    """Chat sometimes omits the email. The placeholder account and a real web account can then both
    match, which used to raise MultipleResultsFound for every later message."""
    first = await get_or_create_google_user(db_session, GoogleChatUser(name="users/200", displayName="Bob"))
    assert first.email == "200@orbit.chat"
    await make_user(db_session, "bob@corp.com")

    again = await get_or_create_google_user(
        db_session, GoogleChatUser(name="users/200", displayName="Bob", email="bob@corp.com")
    )
    assert again.id == first.id  # the established chat identity keeps working


async def test_new_chat_user_gets_a_normalised_email(db_session):
    created = await get_or_create_google_user(
        db_session, GoogleChatUser(name="users/300", displayName="Cy", email="Cy@Corp.com")
    )
    assert created.email == "cy@corp.com"
    again = await get_or_create_google_user(
        db_session, GoogleChatUser(name="users/300", displayName="Cy", email="cy@corp.com")
    )
    assert again.id == created.id


# --- event ledger -----------------------------------------------------------------------------


async def ledger_row(db, key: str) -> ChatEventLedger:
    return (await db.execute(select(ChatEventLedger).where(ChatEventLedger.event_key == key))).scalar_one()


async def test_first_claim_wins_and_a_repeat_is_a_duplicate(db_session):
    assert await chat_events.claim_event("k1", "MESSAGE") == (False, None)
    assert (await chat_events.claim_event("k1", "MESSAGE"))[0] is True


async def test_failed_event_can_be_retried_exactly_once_at_a_time(db_session):
    await chat_events.claim_event("k2", "MESSAGE")
    await chat_events.finalize_event("k2", "boom", status="FAILED")

    first_retry = await chat_events.claim_event("k2", "MESSAGE")
    second_retry = await chat_events.claim_event("k2", "MESSAGE")  # arrives while the first is running
    assert first_retry[0] is False
    assert second_retry[0] is True, "two retries must not both run the side effects"


async def test_a_crashed_in_flight_event_is_eventually_retryable(db_session):
    await chat_events.claim_event("k3", "MESSAGE")
    assert (await chat_events.claim_event("k3", "MESSAGE"))[0] is True  # still in flight: duplicate

    row = await ledger_row(db_session, "k3")
    row.created_at = utc_now() - timedelta(seconds=chat_events.STALE_PROCESSING_SECONDS + 5)
    await db_session.commit()

    assert (await chat_events.claim_event("k3", "MESSAGE"))[0] is False, "a stuck event must not be dropped forever"
    assert (await chat_events.claim_event("k3", "MESSAGE"))[0] is True


async def test_completed_event_returns_the_cached_reply(db_session):
    await chat_events.claim_event("k4", "MESSAGE")
    await chat_events.finalize_event("k4", "hello there")
    assert await chat_events.claim_event("k4", "MESSAGE") == (True, "hello there")
