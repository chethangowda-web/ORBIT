"""Tries the tool-using agent against the real model and the local database.

Creates a few scratch tasks, asks multi-step questions the normal way (through the full agent graph),
prints what happened, then removes the scratch tasks.

Usage (from the repo root, with the local database running):  python backend/scripts/try_tool_agent.py
Free Gemini keys allow only a few requests per minute; the script waits between questions.
"""

import asyncio
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from sqlalchemy import select  # noqa: E402

from agents.orchestrator import process_message  # noqa: E402
from db.base import local_today, utc_now  # noqa: E402
from db.models import Task, User  # noqa: E402
from db.session import async_session_factory  # noqa: E402

PREFIX = "Demo: "
QUESTIONS = [
    "Move the overdue tasks assigned to john@orbit.dev whose title starts with Demo to sarah@orbit.dev and make them high priority",
    "Which of my team has the most overdue work?",
    "Mark every task whose title starts with Demo as done",
]


async def main() -> None:
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None  # run just one question: free keys have tiny quotas
    async with async_session_factory() as db:
        users = {u.email: u for u in (await db.execute(select(User))).scalars().all()}
        sarah, john = users["sarah@orbit.dev"], users["john@orbit.dev"]
    questions = [
        (i, q.format(john=john.display_name, sarah=sarah.display_name))
        for i, q in enumerate(QUESTIONS)
        if only is None or i == only
    ]
    async with async_session_factory() as db:
        today = local_today()
        scratch = [
            Task(title=f"{PREFIX}renew the licence", priority="LOW", status="TODO", created_by_id=sarah.id, assignee_id=john.id, due_date=today - timedelta(days=3)),
            Task(title=f"{PREFIX}send the invoice", priority="LOW", status="TODO", created_by_id=sarah.id, assignee_id=john.id, due_date=today - timedelta(days=2)),
            Task(title=f"{PREFIX}plan the offsite", priority="LOW", status="TODO", created_by_id=sarah.id, assignee_id=john.id, due_date=today + timedelta(days=9)),
        ]
        db.add_all(scratch)
        await db.commit()
        ids = [t.id for t in scratch]

    try:
        for n, (i, question) in enumerate(questions):
            if n:
                await asyncio.sleep(25)  # stay inside a free key's requests-per-minute limit
            started = time.perf_counter()
            state = await process_message(user_id=str(sarah.id), space_id="spaces/try", message=question, thread_id=f"try-{i}")
            took = time.perf_counter() - started
            meta = state.get("trace_metadata") or {}
            print(f"\n>> {question}")
            print(f"   handled by: {state.get('active_agent')}  ({took:.1f}s, classifier={meta.get('classifier')})")
            print(f"   steps: {[(s['node'], s.get('tools')) for s in meta.get('steps', [])]}")
            print("   reply:")
            for line in (state.get("response") or "").splitlines():
                print(f"     {line}")
        async with async_session_factory() as db:
            rows = (await db.execute(select(Task).where(Task.id.in_(ids)))).scalars().all()
            print("\nscratch tasks afterwards:")
            for row in rows:
                owner = users.get(next((e for e, u in users.items() if u.id == row.assignee_id), ""), None)
                print(f"   {row.title:34} assignee={owner.display_name if owner else '?':12} priority={row.priority:8} status={row.status}")
    finally:
        async with async_session_factory() as db:
            for row in (await db.execute(select(Task).where(Task.id.in_(ids)))).scalars().all():
                row.deleted_at = utc_now()
            await db.commit()
        print("\n(scratch tasks removed)")


asyncio.run(main())
