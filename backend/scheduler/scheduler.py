"""Autonomous Scheduler: Configures and manages APScheduler jobs."""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from apscheduler.jobstores.base import BaseJobStore
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from scheduler.jobs.daily_briefing import run_daily_briefing
from scheduler.jobs.overdue_alert import run_overdue_alerts
from scheduler.jobs.weekly_summary import run_weekly_summary

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"


def _create_jobstore() -> Dict[str, BaseJobStore]:
    """Attempts to configure Redis jobstore, falling back to MemoryJobStore on failure."""
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


def register_default_jobs(sched: AsyncIOScheduler) -> None:
    """Registers standard cron triggers for briefings, alerts, and summaries."""
    # 1. Daily Morning Briefing at 9:00 AM IST
    sched.add_job(
        run_daily_briefing,
        trigger=CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="daily_briefing",
        name="Daily Morning Briefing",
        replace_existing=True,
    )

    # 2. Daily Overdue Alerts at 6:00 PM IST
    sched.add_job(
        run_overdue_alerts,
        trigger=CronTrigger(hour=18, minute=0, timezone=TIMEZONE),
        id="overdue_alert",
        name="Daily Overdue Task Alert",
        replace_existing=True,
    )

    # 3. Weekly Summary on Mondays at 9:30 AM IST
    sched.add_job(
        run_weekly_summary,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=TIMEZONE),
        id="weekly_summary",
        name="Weekly Productivity Digest",
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
