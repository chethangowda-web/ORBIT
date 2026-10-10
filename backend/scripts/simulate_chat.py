"""Talk to ORBIT's Google Chat webhook from a terminal, without Google.

It sends the same JSON events Google Chat would, so it exercises the real webhook,
agents, cards and idempotency. Use it to check the bot before wiring up Google.

    python -m scripts.simulate_chat --email john@orbit.dev
    python -m scripts.simulate_chat --email john@orbit.dev --say "Show my pending tasks"

Inside the prompt:
    <text>        send a message (try /tasks, /plan, /overdue, /new Fix login)
    done N        press the Done button of item N from the last card
    confirm       press Confirm on a pending confirmation card
    cancel        press Cancel on a pending confirmation card
    quit          exit

The webhook must have GOOGLE_CHAT_VERIFY_AUTH=false (development). If
GOOGLE_CHAT_WEBHOOK_SECRET is set, this script signs requests with it automatically
(pass --secret or export the variable).
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from typing import Any, Optional

import httpx


class Session:
    def __init__(self, url: str, email: str, name: str, secret: str, space: str, space_type: str):
        self.url, self.secret, self.space, self.space_type = url, secret, space, space_type
        self.user = {"name": f"users/{abs(hash(email)) % 10**9}", "displayName": name, "email": email}
        self.buttons: list[tuple[str, dict[str, str]]] = []
        self.pending_thread: Optional[str] = None

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Goog-Signature"] = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        response = httpx.post(self.url, content=body, headers=headers, timeout=60)
        if response.status_code != 200:
            print(f"! HTTP {response.status_code}: {response.text[:300]}")
            return {}
        return response.json()

    def say(self, text: str) -> dict[str, Any]:
        stamp = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
        slash = {"slashCommand": {"commandId": "0"}} if text.startswith("/") else {}
        payload = {
            "type": "MESSAGE",
            "eventTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "space": {"name": self.space, "type": self.space_type},
            "user": self.user,
            "message": {"name": f"{self.space}/messages/{stamp}", "text": text, **slash},
        }
        return self._post(payload)

    def click(self, action: str, params: dict[str, str]) -> dict[str, Any]:
        payload = {
            "type": "CARD_CLICKED",
            "eventTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + "",
            "space": {"name": self.space, "type": self.space_type},
            "user": self.user,
            "action": {
                "actionMethodName": action,
                "parameters": [{"key": k, "value": v} for k, v in {**params, "_n": uuid.uuid4().hex[:6]}.items()],
            },
        }
        return self._post(payload)

    def show(self, reply: dict[str, Any]) -> None:
        self.buttons = []
        if not reply:
            return
        text = reply.get("text")
        if text:
            print(f"\nORBIT: {text}")
        for card in reply.get("cardsV2", []):
            body = card.get("card", {})
            header = body.get("header", {})
            if header.get("title"):
                print(f"  [card] {header['title']}  {header.get('subtitle', '')}")
            for section in body.get("sections", []):
                for widget in section.get("widgets", []):
                    self._show_widget(widget)

    def _show_widget(self, widget: dict[str, Any]) -> None:
        if "decoratedText" in widget:
            item = widget["decoratedText"]
            label = item.get("text", "").replace("<b>", "").replace("</b>", "")
            line = f"    - {label}  ({item.get('bottomLabel', '')})" if item.get("bottomLabel") else f"    - {item.get('topLabel', '')}: {label}"
            button = item.get("button")
            if button:
                action = button["onClick"]["action"]
                self.buttons.append((action["function"], {p["key"]: p["value"] for p in action.get("parameters", [])}))
                line += f"   [done {len(self.buttons)}]"
            print(line)
        elif "textParagraph" in widget:
            print(f"    {widget['textParagraph'].get('text', '')}")
        elif "buttonList" in widget:
            for b in widget["buttonList"]["buttons"]:
                action = b["onClick"]["action"]
                self.buttons.append((action["function"], {p["key"]: p["value"] for p in action.get("parameters", [])}))
                print(f"    [button] {b['text']}   (type: {'confirm' if 'confirm' in action['function'] else 'cancel' if 'cancel' in action['function'] else action['function']})")


def main() -> int:
    # Replies contain emoji; the default Windows console encoding cannot print them.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Simulate Google Chat against a local ORBIT webhook")
    parser.add_argument("--url", default="http://localhost:8001/api/chat/webhook")
    parser.add_argument("--email", default="john@orbit.dev")
    parser.add_argument("--name", default="Simulated User")
    parser.add_argument("--secret", default=os.environ.get("GOOGLE_CHAT_WEBHOOK_SECRET", ""))
    parser.add_argument("--space", default="spaces/SIMULATED_DM")
    parser.add_argument("--space-type", default="DM", choices=["DM", "ROOM"])
    parser.add_argument("--say", help="send one message and exit")
    args = parser.parse_args()

    chat = Session(args.url, args.email, args.name, args.secret, args.space, args.space_type)
    if args.say:
        chat.show(chat.say(args.say))
        return 0

    print(f"Simulating Google Chat as {args.email}. Type a message, 'done N', 'confirm', 'cancel' or 'quit'.")
    while True:
        try:
            line = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            return 0
        if not line:
            continue
        if line in ("quit", "exit"):
            return 0
        if line.lower().startswith("done "):
            try:
                action, params = chat.buttons[int(line.split()[1]) - 1]
            except (ValueError, IndexError):
                print("! no such button; send a message that returns a card first")
                continue
            chat.show(chat.click(action, params))
        elif line.lower() in ("confirm", "cancel"):
            wanted = "confirm" if line.lower() == "confirm" else "cancel"
            match = next(((a, p) for a, p in chat.buttons if wanted in a), None)
            if not match:
                print("! no confirmation card is pending")
                continue
            chat.show(chat.click(*match))
        else:
            chat.show(chat.say(line))


if __name__ == "__main__":
    sys.exit(main())
