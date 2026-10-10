"""Manual smoke test against a running backend: login, open the SSE stream, change a task, upload and
download a file. Usage: python backend/scripts/live_smoke.py [base_url]"""

import sys
import threading
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001") + "/api"


def main() -> int:
    login = httpx.post(f"{BASE}/auth/token", json={"email": "sarah@orbit.dev", "password": "password123"}, timeout=15)
    login.raise_for_status()
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    frames: list[str] = []
    stop = threading.Event()

    def listen() -> None:
        with httpx.stream("GET", f"{BASE}/events/stream", headers=headers, timeout=None) as resp:
            print("stream status:", resp.status_code, resp.headers.get("content-type"))
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    frames.append(line)
                if stop.is_set():
                    return

    threading.Thread(target=listen, daemon=True).start()
    time.sleep(2)

    task = httpx.post(f"{BASE}/tasks", json={"title": "smoke test task"}, headers=headers, timeout=15).json()["data"]
    time.sleep(1.5)
    print("events after create:", frames)

    up = httpx.post(
        f"{BASE}/tasks/{task['id']}/attachments",
        files={"file": ("notes.txt", b"hello attachments", "text/plain")},
        headers=headers,
        timeout=15,
    )
    print("upload:", up.status_code, up.json()["data"]["filename"] if up.is_success else up.text)
    att = up.json()["data"]
    dl = httpx.get(f"{BASE}/tasks/{task['id']}/attachments/{att['id']}", headers=headers, timeout=15)
    print("download:", dl.status_code, dl.content, dl.headers.get("content-disposition"))
    bad = httpx.post(
        f"{BASE}/tasks/{task['id']}/attachments", files={"file": ("x.html", b"<b>", "text/html")}, headers=headers, timeout=15
    )
    print("html upload rejected:", bad.status_code)

    httpx.delete(f"{BASE}/tasks/{task['id']}", headers=headers, timeout=15)
    stop.set()
    ok = bool(frames) and up.status_code == 201 and dl.content == b"hello attachments" and bad.status_code == 415
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
