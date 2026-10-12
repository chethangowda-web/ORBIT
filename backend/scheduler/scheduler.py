"""Autonomous Scheduler: Configures and manages APScheduler jobs."""

import functools
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse
import redis.asyncio as aioredis
from apscheduler.jobstores.base import BaseJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from scheduler.jobs.daily_briefing import run_daily_briefing
from scheduler.jobs.follow_ups import run_due_soon_reminders, run_manager_escalations, run_stale_nudges
from scheduler.jobs.overdue_alert import run_overdue_alerts
from scheduler.jobs.weekly_summary import run_weekly_summary

logger = logging.getLogger(__name__)

TIMEZONE = settings.APP_TIMEZONE
JOB_LOCK_TTL_SECONDS = 300


def _create_jobstore() -> Dict[str, BaseJobStore]:
    """Attempts to configure Redis jobstore, falling back to MemoryJobStore on failure."""
    if settings.SCHEDULER_JOBSTORE.lower() == "memory":
        return {"default": MemoryJobStore()}
    try:
        import redis
        from apscheduler.jobstores.redis import RedisJobStore

        parsed = urlparse(settings.REDIS_URL)
        db_num = int(parsed.path.lstrip("/")) if parsed.path.lstrip("/") else 0
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379

        r = redis.Redis(
            host=host,
            port=port,
            db=db_num,
            password=parsed.password,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        r.ping()
        logger.info("Scheduler connected to Redis job store (%s:%s/%s)", host, port, db_num)
        return {
            "default": RedisJobStore(
                host=host,
                port=port,
                db=db_num,
                password=parsed.password,
                jobs_key="orbit:jobs",
                run_times_key="orbit:job_run_times",
            )
        }
    except Exception as exc:
        logger.warning(
            "Redis job store unavailable (%s). Falling back to in-memory job store.", exc
        )
        return {"default": MemoryJobStore()}


scheduler = AsyncIOScheduler(
    jobstores=_create_jobstore(),
    timezone=TIMEZONE,
)


def with_job_lock(name: str, job: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Wrap a job so only one worker runs it per firing.

    Uses a Redis ``SET NX EX`` lock (``orbit:lock:scheduler:<name>``). If Redis is
    unreachable the job runs anyway: the jobs themselves dedupe through
    ``notification_logs``, so a missed lock degrades to a rare duplicate check
    rather than a missed digest.
    """

    @functools.wraps(job)
    async def locked(*args: Any, **kwargs: Any) -> Any:
        client = None
        key = f"orbit:lock:scheduler:{name}"
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
            )
            acquired = await client.set(key, "1", nx=True, ex=JOB_LOCK_TTL_SECONDS)
            if not acquired:
                logger.info("Scheduler job %s already running elsewhere; skipping.", name)
                return None
        except Exception as exc:
            logger.warning("Scheduler lock unavailable for %s (%s); running unlocked.", name, exc)
            client = None
        try:
            return await job(*args, **kwargs)
        finally:
            # Keep the lock for its TTL so a second worker firing a moment later
            # cannot re-run the job; nothing to release on purpose.
            if client is not None:
                await client.aclose()

    locked.__orbit_locked__ = True  # type: ignore[attr-defined]
    return locked


# Module-level locked jobs. APScheduler's persistent job stores save a job as a "module:function"
# reference and rebuild it from that; a wrapper created at registration time was saved as the
# *unwrapped* job, so jobs restored from Redis silently ran without their lock.
locked_daily_briefing = with_job_lock("daily_briefing", run_daily_briefing)
locked_overdue_alerts = with_job_lock("overdue_alert", run_overdue_alerts)
locked_weekly_summary = with_job_lock("weekly_summary", run_weekly_summary)
locked_due_soon = with_job_lock("due_soon_reminder", run_due_soon_reminders)
locked_stale_nudges = with_job_lock("stale_nudge", run_stale_nudges)
locked_escalations = with_job_lock("manager_escalation", run_manager_escalations)
for _fn, _name in (
    (locked_daily_briefing, "locked_daily_briefing"),
    (locked_overdue_alerts, "locked_overdue_alerts"),
    (locked_weekly_summary, "locked_weekly_summary"),
    (locked_due_soon, "locked_due_soon"),
    (locked_stale_nudges, "locked_stale_nudges"),
    (locked_escalations, "locked_escalations"),
):
    _fn.__name__ = _name
    _fn.__qualname__ = _name
    _fn.__module__ = __name__


def register_default_jobs(sched: AsyncIOScheduler) -> None:
    """Registers standard cron triggers for briefings, alerts, and summaries."""
    # 1. Daily Morning Briefing at 9:00 AM IST
    sched.add_job(
        locked_daily_briefing,
        trigger=CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="daily_briefing",
        name="Daily Morning Briefing",
        replace_existing=True,
    )

    # 2. Daily Overdue Alerts at 6:00 PM IST
    sched.add_job(
        locked_overdue_alerts,
        trigger=CronTrigger(hour=18, minute=0, timezone=TIMEZONE),
        id="overdue_alert",
        name="Daily Overdue Task Alert",
        replace_existing=True,
    )

    # 3. Weekly Summary on Mondays at 9:30 AM IST
    sched.add_job(
        locked_weekly_summary,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=TIMEZONE),
        id="weekly_summary",
        name="Weekly Productivity Digest",
        replace_existing=True,
    )

    # 4. Reminder about tasks due tomorrow, every day at 4:00 PM
    sched.add_job(
        locked_due_soon,
        trigger=CronTrigger(hour=16, minute=0, timezone=TIMEZONE),
        id="due_soon_reminder",
        name="Due-Tomorrow Reminder",
        replace_existing=True,
    )

    # 5. Check-in on tasks that went quiet, weekdays at 11:00 AM
    sched.add_job(
        locked_stale_nudges,
        trigger=CronTrigger(day_of_week="mon-fri", hour=11, minute=0, timezone=TIMEZONE),
        id="stale_nudge",
        name="Quiet Task Check-in",
        replace_existing=True,
    )

    # 6. Late-work summary for managers, weekdays at 5:30 PM
    sched.add_job(
        locked_escalations,
        trigger=CronTrigger(day_of_week="mon-fri", hour=17, minute=30, timezone=TIMEZONE),
        id="manager_escalation",
        name="Late Work Summary",
        replace_existing=True,
    )


def start_scheduler() -> None:
    """Starts the background scheduler if enabled and not already running."""
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled by configuration (SCHEDULER_ENABLED=False).")
        return

    if not scheduler.running:
        register_default_jobs(scheduler)
        scheduler.start()
        logger.info("Autonomous scheduler started successfully.")


def stop_scheduler() -> None:
    """Safely shuts down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Autonomous scheduler shut down.")


def get_scheduler_status() -> Dict[str, Any]:
    """Returns runtime health and list of scheduled jobs."""
    jobs: List[Dict[str, Any]] = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": (
                        job.next_run_time.isoformat() if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                }
            )

    return {
        "running": scheduler.running,
        "job_count": len(jobs),
        "jobs": jobs,
        "timezone": TIMEZONE,
    }
