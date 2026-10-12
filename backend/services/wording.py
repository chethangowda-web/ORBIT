"""Plain-language helpers for text people read (kept dependency-free so any module can import it)."""

from typing import Any


def friendly(value: Any) -> str:
    """"IN_PROGRESS" -> "In progress", "HIGH" -> "High"."""
    text = str(value or "").split(".")[-1].replace("_", " ").strip().lower()
    return text[:1].upper() + text[1:]
