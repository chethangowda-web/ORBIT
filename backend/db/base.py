"""
ORBIT Database Base Model
Provides declarative base for all SQLAlchemy ORM models.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime

from config import settings


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


def app_tz() -> ZoneInfo:
    """The product timezone that defines 'today' for due dates and digests."""
    return ZoneInfo(settings.APP_TIMEZONE)


def local_now() -> datetime:
    """Current time in the product timezone."""
    return datetime.now(app_tz())


def local_today() -> date:
    """Today's calendar date in the product timezone (not the server's)."""
    return local_now().date()


def local_midnight_utc() -> datetime:
    """Start of the current product-timezone day, expressed in UTC."""
    start = local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all database models."""
    pass
