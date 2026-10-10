"""Expose your local ORBIT backend to Google Chat with one command.

    python -m scripts.dev_tunnel            # tunnels http://localhost:8001
    python -m scripts.dev_tunnel --port 8001 --no-check

It starts a free Cloudflare "quick tunnel" (cloudflared), prints the exact endpoint URL to paste
into Google Cloud, copies it to the clipboard on Windows, and sends a test event through the
tunnel to prove the whole path works. Keep this window open: when it stops, Chat shows
"ORBIT not responding". The URL changes on every start, so paste it again after a restart.
For a permanent URL use a named Cloudflare tunnel or deploy the backend (docs/GOOGLE_CHAT_SETUP.md).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Optional

TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
WINDOWS_PATHS = [
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
]


def find_cloudflared() -> Optional[str]:
    """cloudflared on PATH, or in its usual Windows install folders."""
    found = shutil.which("cloudflared")
    if found:
        return found
    return next((p for p in WINDOWS_PATHS if os.path.exists(p)), None)


def extract_tunnel_url(line: str) -> Optional[str]:
    match = TUNNEL_URL.search(line)
    return match.group(0) if match else None


def endpoint_for(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat/webhook"


def check_endpoint(endpoint: str, timeout: float = 30.0) -> tuple[bool, str]:
    """POST a harmless 'help' event through the tunnel; returns (ok, detail)."""
    event = {
        "type": "MESSAGE",
        "space": {"name": "spaces/TUNNEL_CHECK", "type": "DM"},
        "user": {"name": "users/0", "displayName": "Tunnel check", "email": "tunnel-check@orbit.chat"},
        "message": {"name": f"spaces/TUNNEL_CHECK/messages/{int(time.time())}", "text": "help"},
    }
    request = urllib.request.Request(
        endpoint, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode())
            return True, str(body.get("text", ""))[:60]
    except urllib.error.HTTPError as err:
        hint = " (webhook authentication is on: the tunnel works, but this unsigned test is rejected)" if err.code in (401, 403) else ""
        return err.code in (401, 403), f"HTTP {err.code}{hint}"
    except Exception as err:  # connection refused, DNS not ready yet, timeout
        return False, str(err)


def copy_to_clipboard(text: str) -> bool:
    if os.name != "nt":
        return False
    try:
        subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Tunnel the local ORBIT API to the internet for Google Chat")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--no-check", action="store_true", help="skip the end-to-end test event")
    args = parser.parse_args()

    binary = find_cloudflared()
    if not binary:
        print("cloudflared was not found. Install it (Windows: winget install Cloudflare.cloudflared) and retry.")
        return 1

    try:
        urllib.request.urlopen(f"http://localhost:{args.port}/health", timeout=5).read()
    except Exception:
        print(f"Nothing is answering on http://localhost:{args.port}/health. Start the ORBIT backend first.")
        return 1

    process = subprocess.Popen(
        [binary, "tunnel", "--url", f"http://localhost:{args.port}", "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    found: dict[str, str] = {}

    def watch() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            url = extract_tunnel_url(line)
            if url and "url" not in found:
                found["url"] = url

    threading.Thread(target=watch, daemon=True).start()

    deadline = time.time() + 60
    while "url" not in found and time.time() < deadline and process.poll() is None:
        time.sleep(0.5)
    if "url" not in found:
        print("The tunnel did not come up within 60 seconds. Check your internet connection.")
        process.terminate()
        return 1

    endpoint = endpoint_for(found["url"])
    copied = copy_to_clipboard(endpoint)
    print("\n" + "=" * 72)
    print("Paste this as the HTTP endpoint URL in Google Cloud Console:")
    print("  Google Chat API > Configuration > Connection settings\n")
    print(f"    {endpoint}\n")
    print("(copied to your clipboard)" if copied else "")
    print("=" * 72)

    if not args.no_check:
        for attempt in range(1, 7):  # a fresh tunnel needs a few seconds for DNS
            ok, detail = check_endpoint(endpoint)
            if ok:
                print(f"End-to-end check passed through the tunnel: {detail}")
                break
            time.sleep(4)
        else:
            print(f"Warning: the test event did not get through yet ({detail}). Wait a few seconds and try again from Chat.")

    print("\nTunnel is running. Press Ctrl+C to stop it (Chat will then show 'ORBIT not responding').")
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
