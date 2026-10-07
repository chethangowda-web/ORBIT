"""
ORBIT Database Base Model
Provides declarative base for all SQLAlchemy ORM models.
"""

from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime


def utc_now() -> datetime:
    """Return current UTC timestamp with timezone."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarative class for all database models."""
    pass
