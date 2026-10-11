"""Sends a few messages to a running backend and prints which agents and tools handled each one.
Usage: python backend/scripts/show_agent_run.py [base_url] [email] [password]"""

import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001") + "/api"
EMAIL = sys.argv[2] if len(sys.argv) > 2 else "sarah@orbit.dev"
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "password123"

MESSAGES = [
    "what should I focus on today?",
    "who on the team is overloaded?",
    "show my overdue tasks",
    "create a high priority task to review the contract by Friday",
]


def main() -> None:
    login = httpx.post(f"{BASE}/auth/token", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    created = None
    for message in MESSAGES:
        res = httpx.post(f"{BASE}/chat/query", json={"message": message}, headers=headers, timeout=60)
        data = res.json()["data"]
        meta = data.get("metadata") or {}
        print(f"\n>> {message}")
        print(f"   intent={meta.get('intent')}  agents={' -> '.join(meta.get('agents_invoked') or [])}")
        print(f"   tools={', '.join(meta.get('tool_calls_made') or []) or '-'}  took={meta.get('total_duration_ms')} ms")
        print("   reply:", " | ".join((data.get("response") or "").splitlines()[:3])[:220])
        for task in data.get("referenced_tasks") or []:
            created = task.get("id") or created
    traces = httpx.get(f"{BASE}/chat/traces", params={"limit": 3}, headers=headers, timeout=30).json()["data"]
    print("\nlatest stored traces:", [(t["intent"], t["status"], t["agents_invoked"]) for t in traces["items"]])
    if created:
        httpx.delete(f"{BASE}/tasks/{created}", headers=headers, timeout=30)


main()
