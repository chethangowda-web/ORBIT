"""Scheduler: the job lock must survive the job store, and duplicate checks must tolerate repeats."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.util import ref_to_obj
from sqlalchemy import select

from db.base import utc_now
from db.models import NotificationLog, User
from scheduler import scheduler as sched_module
from scheduler.jobs import daily_briefing, overdue_alert, weekly_summary


def test_registered_jobs_keep_their_lock_when_restored_from_a_job_store():
    """With the Redis job store a job is saved as a "module:function" reference and rebuilt from it.
    The old functools.wraps wrapper was saved as the *unwrapped* job, so a restored job ran without
    its lock and every worker would send the same digest."""
    sched = AsyncIOScheduler(timezone="Asia/Kolkata")
    sched_module.register_default_jobs(sched)
    jobs = sched.get_jobs()
    assert {j.id for j in jobs} == {"daily_briefing", "overdue_alert", "weekly_summary"}
    for job in jobs:
        restored = ref_to_obj(job.func_ref)
        assert getattr(restored, "__orbit_locked__", False), f"{job.id} would run unlocked after a restart"


async def add_sent_logs(db, user: User, log_type: str, count: int) -> None:
    for _ in range(count):
        db.add(
            NotificationLog(user_id=user.id, type=log_type, message="x", status="sent", sent_at=utc_now())
        )
    await db.commit()


async def test_repeated_sends_do_not_break_the_already_received_checks(db_session, seed_test_user):
    """A forced admin trigger leaves several 'sent' rows for one user and day; the next regular run
    used to raise MultipleResultsFound and abort the whole job for everyone."""
    for module, fn_name, log_type in (
        (daily_briefing, "_has_already_received_briefing", "daily_briefing"),
        (overdue_alert, "_has_already_received_overdue_alert", "overdue_alert"),
        (weekly_summary, "_has_already_received_weekly_summary", "weekly_summary"),
    ):
        await add_sent_logs(db_session, seed_test_user, log_type, 2)
        check = getattr(module, fn_name)
        assert await check(db_session, seed_test_user.id) is True
    rows = (await db_session.execute(select(NotificationLog))).scalars().all()
    assert len(rows) == 6
