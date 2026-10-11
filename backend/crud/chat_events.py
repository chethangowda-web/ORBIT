"""
Chat Event Idempotency Ledger
Prevents duplicate side effects when Google Chat redelivers the same event.
"""

import hashlib
import json
import logging
from datetime import timedelta
from typing import Optional, Tuple
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import utc_now
from db.models import ChatEventLedger
from tools.base import get_tool_session

logger = logging.getLogger(__name__)

# An event still "processing" after this long belongs to a worker that died; redelivery may retry it.
STALE_PROCESSING_SECONDS = 120


def compute_event_key(
    event_type: str,
    space_name: str,
    user_name: Optional[str],
    event_time: Optional[str],
    discriminator: str,
) -> str:
    """Derives a stable idempotency key for an inbound Google Chat event.

    Google Chat does not guarantee a single global event ID across all payload
    shapes (standard events vs. Workspace Add-on commonEventObject), so the key
    is built from the fields that are stable across a genuine redelivery of the
    *same* event but distinct across a new user action (space, sender, server
    event timestamp, and a type-specific discriminator such as the message
    resource name or action+parameters).
    """
    raw = json.dumps(
        {
            "type": event_type,
            "space": space_name,
            "user": user_name,
            "event_time": event_time,
            "discriminator": discriminator,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{event_type}:{digest}"


async def claim_event(event_key: str, event_type: str) -> Tuple[bool, Optional[str]]:
    """Atomically claims an event for processing.

    Returns (is_duplicate, cached_response_text). When is_duplicate is True,
    the caller must not re-execute any side-effecting logic and should reuse
    the cached response (if available) or return a safe generic acknowledgement.
    """
    async with get_tool_session() as session:  # type: AsyncSession
        existing = await session.execute(
            select(ChatEventLedger).where(ChatEventLedger.event_key == event_key)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            if row.status == "COMPLETED":
                return True, row.response_text

            # FAILED, or PROCESSING for so long that its worker must have died: a retry may re-run.
            # The takeover is ONE conditional UPDATE, so of several simultaneous retries exactly
            # one changes the row and the rest see it as in flight. created_at doubles as the
            # "claimed at" time.
            now = utc_now()
            takeover = await session.execute(
                update(ChatEventLedger)
                .where(
                    ChatEventLedger.event_key == event_key,
                    or_(
                        ChatEventLedger.status == "FAILED",
                        and_(
                            ChatEventLedger.status == "PROCESSING",
                            ChatEventLedger.created_at < now - timedelta(seconds=STALE_PROCESSING_SECONDS),
                        ),
                    ),
                )
                .values(status="PROCESSING", response_text=None, created_at=now)
                .execution_options(synchronize_session=False)
            )
            await session.commit()
            if takeover.rowcount == 1:
                return False, None
            return True, None

        ledger_entry = ChatEventLedger(event_key=event_key, event_type=event_type, status="PROCESSING")
        session.add(ledger_entry)
        try:
            await session.commit()
            return False, None
        except IntegrityError:
            # Concurrent request already claimed this event first.
            await session.rollback()
            return True, None


async def finalize_event(event_key: str, response_text: str, status: str = "COMPLETED") -> None:
    """Records the terminal outcome of event processing for future dedup lookups."""
    async with get_tool_session() as session:  # type: AsyncSession
        try:
            await session.execute(
                update(ChatEventLedger)
                .where(ChatEventLedger.event_key == event_key)
                .values(status=status, response_text=response_text, completed_at=utc_now())
            )
            await session.commit()
        except Exception as exc:
            logger.warning("Failed to finalize chat event ledger entry %s: %s", event_key, exc)
            await session.rollback()
