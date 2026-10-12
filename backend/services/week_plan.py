"""Plan a person's week from their real tasks.

This is scheduling, so it is an algorithm, not a prompt: deterministic, explainable, instant, and it
spends no AI request. Late work goes first, then work due soonest (earliest-deadline-first); each task
is placed on the lightest day that still meets its deadline, so the week is balanced; each day holds a
limited number of tasks; a task that cannot meet its deadline is flagged instead of hidden.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from services.wording import friendly

PER_DAY = 4
WORKING_DAYS = 5
_WEIGHT = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}


@dataclass
class PlannedTask:
    id: str
    title: str
    priority: str
    status: str
    due_date: Optional[date]
    days_late: int = 0
    note: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "status": self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "days_late": self.days_late,
            "note": self.note,
        }


@dataclass
class DayPlan:
    date: date
    tasks: list[PlannedTask] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.date:%A} {self.date.day} {self.date:%b}"


@dataclass
class WeekPlan:
    days: list[DayPlan]
    at_risk: list[PlannedTask] = field(default_factory=list)  # placed, but the day is over capacity
    later: list[PlannedTask] = field(default_factory=list)  # did not fit this week
    late_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "days": [{"date": d.date.isoformat(), "label": d.label, "tasks": [t.to_dict() for t in d.tasks]} for d in self.days],
            "at_risk": [t.to_dict() for t in self.at_risk],
            "later": [t.to_dict() for t in self.later],
            "late_count": self.late_count,
        }


def working_days(start: date, count: int = WORKING_DAYS) -> list[date]:
    """The next `count` weekdays from `start` (a weekend starts on Monday)."""
    days: list[date] = []
    day = start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def _as_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def build_week_plan(tasks: list[dict[str, Any]], today: date, per_day: int = PER_DAY) -> WeekPlan:
    days = working_days(today)
    plan = WeekPlan(days=[DayPlan(d) for d in days])

    items: list[PlannedTask] = []
    for t in tasks:
        due = _as_date(t.get("due_date"))
        late = (today - due).days if due and due < today else 0
        items.append(
            PlannedTask(
                id=str(t.get("id")),
                title=str(t.get("title")),
                priority=str(t.get("priority") or "MEDIUM").split(".")[-1].upper(),
                status=str(t.get("status") or "TODO").split(".")[-1].upper(),
                due_date=due,
                days_late=late,
            )
        )
    plan.late_count = sum(1 for i in items if i.days_late > 0)

    def order(item: PlannedTask):
        return (
            0 if item.days_late > 0 else 1,  # late work first
            item.due_date or date.max,  # then the soonest deadline
            -_WEIGHT.get(item.priority, 1),  # then the most important
            0 if item.status == "IN_PROGRESS" else 1,  # then what is already under way
            item.title.lower(),
        )

    def last_day_index(due: Optional[date]) -> Optional[int]:
        """Index of the last working day on or before the deadline; None when it is after this week or unset."""
        if due is None or due > days[-1]:
            return None
        return max((i for i, d in enumerate(days) if d <= due), default=0)

    for item in sorted(items, key=order):
        latest = last_day_index(item.due_date)
        window = range(len(days)) if (item.days_late > 0 or latest is None) else range(latest + 1)
        open_days = [i for i in window if len(plan.days[i].tasks) < per_day]
        if open_days:
            # Late work goes on the earliest day. Everything else goes on the lightest day that still
            # meets its deadline (earliest on a tie), so the week is balanced, not piled on Monday.
            slot = open_days[0] if item.days_late > 0 else min(open_days, key=lambda i: (len(plan.days[i].tasks), i))
            plan.days[slot].tasks.append(item)
        elif latest is not None and item.days_late == 0:
            # The deadline is this week but every day up to it is full: keep it on its deadline, flagged.
            first, last = plan.days[0].date, plan.days[latest].date
            item.note = (
                f"due {last:%A} but the day is already full"
                if latest == 0
                else f"due {last:%A} but {first:%A} to {last:%A} are already full"
            )
            plan.days[latest].tasks.append(item)
            plan.at_risk.append(item)
        else:
            plan.later.append(item)
    return plan


def _line(task: PlannedTask, flagged: bool) -> str:
    bits = [f"{friendly(task.priority)} priority"]
    if task.days_late:
        bits.append(f"{task.days_late} day{'s' if task.days_late != 1 else ''} late")
    elif task.due_date:
        bits.append(f"due {task.due_date:%a} {task.due_date.day} {task.due_date:%b}")
    return f"• {'⚠️ ' if flagged else ''}*{task.title}* ({', '.join(bits)})"


def format_week_plan(plan: WeekPlan) -> str:
    planned = sum(len(d.tasks) for d in plan.days)
    if planned == 0 and not plan.later:
        return "☀️ *Your week is clear.* Nothing is assigned to you right now."
    flagged_ids = {t.id for t in plan.at_risk}
    first, last = plan.days[0].date, plan.days[-1].date
    lines = [f"🗓️ *Your week* ({first:%a} {first.day} {first:%b} to {last:%a} {last.day} {last:%b})"]
    if plan.late_count:
        lines.append(f"{plan.late_count} task{'s are' if plan.late_count != 1 else ' is'} already late, so those come first.")
    for day in plan.days:
        lines.append(f"\n*{day.label}*")
        lines += [_line(t, t.id in flagged_ids) for t in day.tasks] or ["• Nothing planned"]
    if plan.at_risk:
        lines.append("\n⚠️ *Tight spots*")
        lines += [f"• *{t.title}*: {t.note}." for t in plan.at_risk]
        lines.append("Ask me to move a due date, or hand something to a teammate.")
    if plan.later:
        lines.append(f"\n📌 *Later:* {len(plan.later)} more task{'s' if len(plan.later) != 1 else ''} did not fit this week.")
    return "\n".join(lines)
