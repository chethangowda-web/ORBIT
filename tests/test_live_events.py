"""Live-update hub: publishing, backpressure, auth, and automatic hooks on commit."""

import asyncio

import pytest
from httpx import AsyncClient

from services import events
from services.events import EventHub, event_stream, format_sse, hub


def drain(queue: asyncio.Queue) -> list[dict]:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def test_each_subscriber_gets_its_own_copy():
    h = EventHub()
    a, b = h.subscribe(), h.subscribe()
    h.publish("tasks", "t1")
    assert drain(a) == [{"topic": "tasks", "task_id": "t1"}]
    assert drain(b) == [{"topic": "tasks", "task_id": "t1"}]


def test_slow_subscriber_is_told_to_resync_instead_of_blocking():
    h = EventHub()
    q = h.subscribe()
    for i in range(events.QUEUE_SIZE + 5):
        h.publish("tasks", str(i))
    items = drain(q)
    assert "resync" in {i["topic"] for i in items}
    assert len(items) <= events.QUEUE_SIZE


def test_connection_cap(monkeypatch):
    monkeypatch.setattr(events, "MAX_SUBSCRIBERS", 2)
    h = EventHub()
    assert h.subscribe() and h.subscribe()
    assert h.subscribe() is None


def test_frames_are_valid_sse_and_carry_no_task_data():
    frame = format_sse({"topic": "tasks", "task_id": "abc"})
    assert frame.startswith("event: change\ndata: ") and frame.endswith("\n\n")
    assert "title" not in frame


async def test_stream_sends_heartbeat_then_events_and_cleans_up():
    queue = hub.subscribe()
    before = hub.subscriber_count
    gen = event_stream(queue, heartbeat=0.05)
    assert (await gen.__anext__()).startswith("retry:")
    assert (await gen.__anext__()) == ": keep-alive\n\n"
    hub.publish("tasks", "x")
    assert '"task_id": "x"' in await gen.__anext__()
    await gen.aclose()
    assert hub.subscriber_count == before - 1


async def test_stream_requires_authentication(client: AsyncClient):
    assert (await client.get("/api/events/stream")).status_code == 401
    assert (await client.get("/api/events/stream", headers={"Authorization": "Bearer nonsense"})).status_code == 401


async def test_committing_a_task_publishes_a_hint(client: AsyncClient, user_auth_headers, seed_test_user):
    queue = hub.subscribe()
    try:
        res = await client.post("/api/tasks", json={"title": "Live one"}, headers=user_auth_headers)
        assert res.status_code == 201
        topics = {m["topic"] for m in drain(queue)}
        assert "tasks" in topics
    finally:
        hub.unsubscribe(queue)


async def test_rolled_back_changes_publish_nothing(db_session, seed_test_user):
    from db.models import Task

    queue = hub.subscribe()
    try:
        db_session.add(Task(title="never committed", priority="LOW", status="PENDING", created_by_id=seed_test_user.id))
        await db_session.flush()
        await db_session.rollback()
        assert drain(queue) == []
    finally:
        hub.unsubscribe(queue)


# --- limits and lifetime ------------------------------------------------------------------------


def test_one_user_cannot_hold_all_the_connections():
    h = EventHub()
    mine = [h.subscribe(owner="u1") for _ in range(events.MAX_PER_USER)]
    newest = h.subscribe(owner="u1")  # over the per-user limit: the oldest connection is closed
    assert newest is not None and h.subscriber_count == events.MAX_PER_USER
    assert drain(mine[0])[-1] is None, "the evicted stream is told to end"
    other = h.subscribe(owner="u2")
    assert other is not None, "other users are unaffected"


async def test_a_stream_ends_when_its_lifetime_is_over():
    h = EventHub()
    queue = h.subscribe(owner="u1")
    gen = event_stream(queue, heartbeat=0.02, max_seconds=0.1)
    frames = [frame async for frame in gen]
    assert frames[0].startswith("retry:")


async def test_an_evicted_stream_stops_sending():
    queue = hub.subscribe(owner="evict-test")
    queue.put_nowait(None)
    frames = [frame async for frame in event_stream(queue, heartbeat=0.05)]
    assert frames == ["retry: 3000\n\n"]
