"""Follow-ups ORBIT sends on its own, without being asked.

* Due tomorrow: a reminder to each assignee about tasks due the next day.
* Gone quiet: a check-in about "in progress" tasks nobody has touched for a few days.
* Late work: a summary for managers of tasks that are several days overdue.

Every job honours per-person opt-outs, sends at most one message per person per period, and records
the real delivery outcome (``sent``, ``failed`` or ``skipped``), exactly like the morning briefing.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from crud.users import get_opted_out_user_ids
from db.base import local_midnight_utc, local_today, utc_now
from db.models import NotificationLog, Task, TaskComment, User
from metrics import record_notification
from services.notifications import deliver_with_retry
from tools.base import get_tool_session
from tools.format_tools import friendly

logger = logging.getLogger(__name__)

OPEN_STATUSES_EXCLUDED = ["DONE", "CANCELLED"]
MAX_LISTED = 6
QUIET_DAYS = 3  # an "in progress" task untouched this long gets a check-in
QUIET_NUDGE_INTERVAL_DAYS = 3  # and one person is checked in on at most this often
LATE_DAYS = 3  # managers hear about work at least this many days overdue

DUE_SOON = "due_soon_reminder"
STALE = "stale_nudge"
ESCALATION = "manager_escalation"


def _empty_summary() -> Dict[str, Any]:
    return {"people": 0, "tasks": 0, "sent": 0, "skipped": 0, "failed": 0}


def _bullet(task: Task, extra: str = "") -> str:
    return f"• *{task.title}* ({friendly(task.priority)} priority{extra})"


def _more(total: int) -> str:
    return f"\n…and {total - MAX_LISTED} more." if total > MAX_LISTED else ""


async def _already_sent_since(session: AsyncSession, user_id: Any, type_: str, since: Any) -> bool:
    row = await session.execute(
        select(NotificationLog.id).where(
            NotificationLog.user_id == user_id,
            NotificationLog.type == type_,
            NotificationLog.status == "sent",
            NotificationLog.sent_at >= since,
        )
    )
    # first(), not scalar_one_or_none(): a forced run can leave several 'sent' rows
    return row.scalars().first() is not None


async def _send(session: AsyncSession, user: User, type_: str, message: str) -> str:
    """Deliver, log the real outcome, and return it."""
    status, error = await deliver_with_retry(user, message)
    record_notification(type_, status)
    session.add(
        NotificationLog(
            user_id=user.id,
            type=type_,
            message=message,
            google_space_id=user.google_space_id or user.google_id,
            status=status,
            error_msg=error,
            sent_at=utc_now(),
        )
    )
    await session.commit()
    return status


async def _deliver_to_each(
    session: AsyncSession,
    groups: Dict[Any, List[Task]],
    type_: str,
    build_message,
    since: Any,
    force: bool,
    summary: Dict[str, Any],
) -> None:
    opted_out = await get_opted_out_user_ids(session, type_)
    summary["people"] = len(groups)
    for user, tasks in groups.items():
        if user.id in opted_out or (not force and await _already_sent_since(session, user.id, type_, since)):
            summary["skipped"] += 1
            continue
        try:
            outcome = await _send(session, user, type_, build_message(user, tasks))
            summary[outcome] = summary.get(outcome, 0) + 1
        except Exception as err:
            logger.error("Could not send %s to %s: %s", type_, user.id, err)
            summary["failed"] += 1


def _group_by_assignee(tasks: List[Task]) -> Dict[Any, List[Task]]:
    groups: Dict[Any, List[Task]] = {}
    for task in tasks:
        if task.assignee and task.assignee.is_active:
            groups.setdefault(task.assignee, []).append(task)
    return groups


# --- due tomorrow ----------------------------------------------------------------------------------


def _due_soon_message(user: User, tasks: List[Task]) -> str:
    first = (user.display_name or "there").split()[0]
    lines = [f"⏰ *Due tomorrow*", f"Hi {first}, {'this is' if len(tasks) == 1 else 'these are'} due tomorrow:"]
    lines += [_bullet(t) for t in tasks[:MAX_LISTED]]
    return "\n".join(lines) + _more(len(tasks)) + "\n\nNeed more time? Just tell me and I'll move the due date."


async def run_due_soon_reminders(session: Optional[AsyncSession] = None, force: bool = False) -> Dict[str, Any]:
    summary = _empty_summary()
    async with get_tool_session(session) as s:
        tomorrow = local_today() + timedelta(days=1)
        rows = await s.execute(
            select(Task)
            .where(Task.deleted_at.is_(None), Task.status.not_in(OPEN_STATUSES_EXCLUDED), Task.due_date == tomorrow)
            .options(selectinload(Task.assignee))
        )
        tasks = list(rows.scalars().all())
        summary["tasks"] = len(tasks)
        await _deliver_to_each(s, _group_by_assignee(tasks), DUE_SOON, _due_soon_message, local_midnight_utc(), force, summary)
    return summary


# --- tasks that went quiet ---------------------------------------------------------------------------


def _stale_message(user: User, tasks: List[Task]) -> str:
    first = (user.display_name or "there").split()[0]
    lines = [f"💤 *Still working on {'this' if len(tasks) == 1 else 'these'}?*", f"Hi {first}, nothing has changed on {'this task' if len(tasks) == 1 else 'these tasks'} for {QUIET_DAYS} days or more:"]
    lines += [_bullet(t) for t in tasks[:MAX_LISTED]]
    return "\n".join(lines) + _more(len(tasks)) + "\n\nTell me if one is done, or if its due date should move."


async def run_stale_nudges(session: Optional[AsyncSession] = None, force: bool = False) -> Dict[str, Any]:
    summary = _empty_summary()
    async with get_tool_session(session) as s:
        cutoff = utc_now() - timedelta(days=QUIET_DAYS)
        recently_discussed = exists().where(TaskComment.task_id == Task.id, TaskComment.created_at >= cutoff)
        rows = await s.execute(
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.status == "IN_PROGRESS",
                Task.updated_at < cutoff,
                ~recently_discussed,  # a task people are commenting on is not quiet
            )
            .options(selectinload(Task.assignee))
        )
        tasks = list(rows.scalars().all())
        summary["tasks"] = len(tasks)
        await _deliver_to_each(
            s, _group_by_assignee(tasks), STALE, _stale_message, utc_now() - timedelta(days=QUIET_NUDGE_INTERVAL_DAYS), force, summary
        )
    return summary


# --- late work, for managers -----------------------------------------------------------------------------


def _late_message(manager: User, tasks: List[Task]) -> str:
    today = local_today()
    ordered = sorted(tasks, key=lambda t: t.due_date)
    lines = [f"🚨 *Late work needs attention*", f"{len(tasks)} task{'s are' if len(tasks) != 1 else ' is'} more than {LATE_DAYS} days late:"]
    for task in ordered[:MAX_LISTED]:
        owner = task.assignee.display_name if task.assignee else "nobody"
        lines.append(_bullet(task, extra=f", {owner}, {(today - task.due_date).days} days late"))
    return "\n".join(lines) + _more(len(tasks)) + "\n\nYou may want to check in with the owners or move the due dates."


async def run_manager_escalations(session: Optional[AsyncSession] = None, force: bool = False) -> Dict[str, Any]:
    summary = _empty_summary()
    async with get_tool_session(session) as s:
        cutoff = local_today() - timedelta(days=LATE_DAYS)
        rows = await s.execute(
            select(Task)
            .where(
                Task.deleted_at.is_(None),
                Task.status.not_in(OPEN_STATUSES_EXCLUDED),
                Task.due_date.is_not(None),
                Task.due_date <= cutoff,
            )
            .options(selectinload(Task.assignee))
        )
        tasks = list(rows.scalars().all())
        summary["tasks"] = len(tasks)
        if not tasks:
            return summary
        managers = (
            await s.execute(select(User).where(User.is_active.is_(True), User.role.in_(["manager", "admin"])))
        ).scalars().all()
        await _deliver_to_each(s, {m: tasks for m in managers}, ESCALATION, _late_message, local_midnight_utc(), force, summary)
    return summary
