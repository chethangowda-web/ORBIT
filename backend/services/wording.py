"""Plain-language helpers for text people read (kept dependency-free so any module can import it)."""

from typing import Any


def friendly(value: Any) -> str:
    """"IN_PROGRESS" -> "In progress", "HIGH" -> "High"."""
    text = str(value or "").split(".")[-1].replace("_", " ").strip().lower()
    return text[:1].upper() + text[1:]


def due_phrase(due: Any, today: Any = None) -> str:
    """A due date the way a person says it: "due today", "due Friday", "due 16 Oct", "2 days late", "no due date"."""
    from datetime import date, datetime, timedelta

    if due in (None, ""):
        return "no due date"
    if isinstance(due, datetime):
        due = due.date()
    elif not isinstance(due, date):
        try:
            due = date.fromisoformat(str(due)[:10])
        except ValueError:
            return f"due {due}"
    if today is None:
        from db.base import local_today

        today = local_today()
    days = (due - today).days
    if days < 0:
        return "1 day late" if days == -1 else f"{-days} days late"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    if days < 7:
        return f"due {due:%A}"
    return f"due {due.day} {due:%b}"
