"""
Task Event Notification Dispatcher
Delivers Google Chat notifications for task assignment, updates, and completion,
regardless of whether the mutation originated from the dashboard or Google Chat.
Reuses the existing Google Chat service and NotificationLog audit model.
"""

import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import utc_now
from db.models import NotificationLog, Task, User
from services.google_chat import send_dm, send_text_message

logger = logging.getLogger(__name__)

# Bounded retry policy for transient outbound delivery failures.
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 1.5
DISPATCH_TIMEOUT_SECONDS = 8.0

PRIORITY_ICONS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🟢",
}


def _format_task_event_message(event_type: str, task: Task, actor_name: str) -> str:
    """Builds a sanitized, recipient-safe notification message for a task event."""
    icon = PRIORITY_ICONS.get(task.priority, "⚪")
    due = task.due_date.isoformat() if task.due_date else "No due date"

    if event_type == "task_assigned":
        return (
            f"📌 *New Task Assigned*\n"
            f"{icon} *{task.title}* (Priority: {task.priority})\n"
            f"Assigned by: {actor_name}\n"
            f"Due: {due}"
        )
    if event_type == "task_updated":
        return (
            f"✏️ *Task Updated*\n"
            f"{icon} *{task.title}* (Priority: {task.priority}, Status: {task.status})\n"
            f"Updated by: {actor_name}\n"
            f"Due: {due}"
        )
    if event_type == "task_completed":
        return (
            f"✅ *Task Completed*\n"
            f"*{task.title}* was marked done by {actor_name}."
        )
    return f"ℹ️ Task *{task.title}* changed."


async def _deliver_with_retry(recipient: User, message: str) -> tuple[str, Optional[str]]:
    """Attempts delivery with bounded retries. Returns (status, error_msg)."""
    if not recipient.google_id and not recipient.google_space_id:
        return "skipped", "Recipient has no linked Google Chat handle"

    last_error: Optional[str] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            if recipient.google_id:
                delivered = await send_dm(recipient.google_id, message)
            else:
                delivered = await send_text_message(recipient.google_space_id, message)  # type: ignore[arg-type]

            if delivered:
                return "sent", None
            last_error = "Google Chat API returned a non-success status"
        except Exception as exc:  # pragma: no cover - defensive, send_* already catches most errors
            last_error = str(exc)

        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    return "failed", last_error


async def notify_task_event(
    session: AsyncSession,
    task: Task,
    event_type: str,
    recipient: Optional[User],
    actor_name: str,
) -> None:
    """Fire-and-forget-safe notification dispatch for a task mutation.

    Never raises: the task mutation that triggered this call has already been
    committed, so a notification failure must not roll it back or surface as
    an error to the caller. Delivery outcome is always recorded in
    NotificationLog so success is never claimed without API confirmation.
    """
    if recipient is None:
        return

    message = _format_task_event_message(event_type, task, actor_name)

    try:
        status, error_msg = await asyncio.wait_for(
            _deliver_with_retry(recipient, message), timeout=DISPATCH_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        status, error_msg = "failed", "Notification dispatch timed out"
    except Exception as exc:  # pragma: no cover - absolute safety net
        status, error_msg = "failed", str(exc)

    try:
        log_entry = NotificationLog(
            user_id=recipient.id,
            type=event_type,
            message=message,
            google_space_id=recipient.google_space_id or recipient.google_id,
            status=status,
            error_msg=error_msg,
            sent_at=utc_now(),
        )
        session.add(log_entry)
        await session.commit()
    except Exception as exc:
        logger.warning("Failed to persist notification log for task %s: %s", task.id, exc)
        await session.rollback()
