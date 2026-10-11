"""Checks that the configured Gemini key and model answer, and how fast.
Usage (from the repo root): python backend/scripts/check_llm.py [model]
Prints no secrets."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from config import settings  # noqa: E402


def main() -> int:
    key = settings.GOOGLE_GEMINI_API_KEY
    if not key:
        print("GOOGLE_GEMINI_API_KEY is not set")
        return 1
    model = (sys.argv[1] if len(sys.argv) > 1 else settings.DEFAULT_LLM_MODEL).split("/")[-1]
    print(f"configured model: {settings.DEFAULT_LLM_MODEL}")

    started = time.perf_counter()
    listing = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", params={"key": key, "pageSize": 100}, timeout=30)
    print(f"list models -> HTTP {listing.status_code} in {time.perf_counter() - started:.1f}s")
    if listing.is_success:
        names = [m["name"].split("/")[-1] for m in listing.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        print("models you can call:", ", ".join(sorted(names)[:25]))
        print(f"'{model}' available:", model in names)
    else:
        print(listing.text[:300].replace(key, "<key>"))

    started = time.perf_counter()
    try:
        res = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]},
            timeout=60,
        )
        print(f"generate with '{model}' -> HTTP {res.status_code} in {time.perf_counter() - started:.1f}s")
        print(res.text[:300].replace(key, "<key>"))
    except Exception as exc:  # noqa: BLE001
        print(f"generate failed after {time.perf_counter() - started:.1f}s: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
