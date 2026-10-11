"""
Live-update event hub.

Mutations of tasks and comments (from the REST API, Google Chat, or the scheduler) publish a
tiny "something changed" hint. Connected dashboards receive it over Server-Sent Events and
refetch through the normal, authorised REST endpoints. The hint carries no task data, so the
stream cannot leak anything a user is not allowed to read.

The hub is in-process: one backend process per deployment. Running several workers would need a
shared bus (Redis pub/sub); the dashboard keeps polling as a fallback so it still converges.
"""

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_SUBSCRIBERS = 200
MAX_PER_USER = 5  # one account (or one script) must not be able to use up every connection
QUEUE_SIZE = 64
HEARTBEAT_SECONDS = 15.0
# A stream is authenticated only when it opens. Ending it after this long (or at the token's expiry,
# whichever is sooner) makes the browser reconnect, which checks the token and the account again.
MAX_STREAM_SECONDS = 30 * 60

WATCHED_TABLES = {"tasks": "tasks", "task_comments": "comments", "task_attachments": "attachments"}


class EventHub:
    def __init__(self) -> None:
        # queue -> owner (a user id, or None); insertion order is connection order
        self._subscribers: dict[asyncio.Queue, Optional[str]] = {}

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def subscribe(self, owner: Optional[str] = None) -> Optional[asyncio.Queue]:
        """Returns a queue, or None when the server is at its global connection cap.

        When `owner` already has MAX_PER_USER streams, the oldest of theirs is closed to make room
        (a reloaded tab leaves its old stream behind for a moment; evicting beats refusing)."""
        if owner is not None:
            mine = [q for q, o in self._subscribers.items() if o == owner]
            while len(mine) >= MAX_PER_USER:
                self._close(mine.pop(0))
        if len(self._subscribers) >= MAX_SUBSCRIBERS:
            return None
        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers[queue] = owner
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.pop(queue, None)

    def _close(self, queue: asyncio.Queue) -> None:
        """Tells a stream to end: its generator stops when it reads None."""
        self.unsubscribe(queue)
        try:
            while True:
                queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(None)

    def publish(self, topic: str, task_id: Optional[str] = None) -> None:
        """Never blocks and never raises. A subscriber that fell behind is told to resync."""
        payload = {"topic": topic, "task_id": task_id}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    while True:
                        queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                queue.put_nowait({"topic": "resync", "task_id": None})


hub = EventHub()


def format_sse(payload: dict) -> str:
    return f"event: change\ndata: {json.dumps(payload)}\n\n"


async def event_stream(
    queue: asyncio.Queue,
    heartbeat: float = HEARTBEAT_SECONDS,
    max_seconds: float = MAX_STREAM_SECONDS,
) -> AsyncIterator[str]:
    """Yields SSE frames until cancelled, evicted (None) or past its lifetime. Comment heartbeats
    keep proxies from closing the socket."""
    deadline = time.monotonic() + max_seconds
    try:
        yield "retry: 3000\n\n"
        while time.monotonic() < deadline:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=min(heartbeat, max(0.0, deadline - time.monotonic())))
            except asyncio.TimeoutError:
                if time.monotonic() >= deadline:
                    break
                yield ": keep-alive\n\n"
                continue
            if payload is None:
                break
            yield format_sse(payload)
    finally:
        hub.unsubscribe(queue)


# --- Automatic publishing -------------------------------------------------------------------
# Every committed change to a watched table publishes once, whatever code path made it.

_PENDING_KEY = "orbit_pending_events"


@event.listens_for(Session, "after_flush")
def _collect_changes(session: Session, _context) -> None:
    pending: dict = session.info.setdefault(_PENDING_KEY, {})
    for obj in list(session.new) + list(session.dirty) + list(session.deleted):
        table = getattr(obj, "__tablename__", None)
        topic = WATCHED_TABLES.get(table)
        if topic is None:
            continue
        task_id = getattr(obj, "id", None) if table == "tasks" else getattr(obj, "task_id", None)
        pending[(topic, str(task_id) if task_id else None)] = True


@event.listens_for(Session, "after_commit")
def _publish_changes(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, None)
    if not pending:
        return
    for topic, task_id in pending:
        try:
            hub.publish(topic, task_id)
        except Exception:  # pragma: no cover - publishing must never break a commit
            logger.exception("Failed to publish live-update event")


@event.listens_for(Session, "after_rollback")
def _discard_changes(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)
