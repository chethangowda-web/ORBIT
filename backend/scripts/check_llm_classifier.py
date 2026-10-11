"""Runs the real intent classifier against the real Gemini model and compares it with the offline rules.
Usage (from backend/): DEFAULT_LLM_MODEL=gemini/gemini-2.5-flash python scripts/check_llm_classifier.py
Prints no secrets."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.supervisor import classify_intent  # noqa: E402
from config import settings  # noqa: E402
from services.llm import fallback_intent_classifier  # noqa: E402

CASES = [
    "Create a high priority task for John to deploy the frontend by Friday",
    "what should I focus on today?",
    "mark the CRM deployment task as done",
    "who on the team is overloaded?",
    "could you push the login bug deadline to next Monday",
    "hello there",
]


async def main() -> None:
    print("model:", settings.DEFAULT_LLM_MODEL)
    for text in CASES:
        started = time.perf_counter()
        result = await classify_intent(text)
        took = time.perf_counter() - started
        offline = fallback_intent_classifier(text)
        source = "LLM" if took > 0.3 else "rules"
        print(f"{took:5.1f}s [{source:5}] {result.intent.value:20} (offline: {offline.intent.value:20}) {text}")


asyncio.run(main())
