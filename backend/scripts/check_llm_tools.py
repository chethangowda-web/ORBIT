"""Does a model support function calling with this key, and how fast? One tiny request per model.
Usage (repo root): python backend/scripts/check_llm_tools.py model1 model2 ...   (no secrets are printed)"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import litellm  # noqa: E402

from config import settings  # noqa: E402

litellm.suppress_debug_info = True
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Find tasks by assignee name.",
            "parameters": {"type": "object", "properties": {"assignee_name": {"type": "string"}}, "required": []},
        },
    }
]


async def probe(model: str) -> None:
    started = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": "Show John's tasks."}],
                tools=TOOLS,
                tool_choice="auto",
                api_key=settings.GOOGLE_GEMINI_API_KEY,
                max_tokens=200,
            ),
            timeout=40,
        )
        msg = response.choices[0].message
        calls = [(c.function.name, c.function.arguments) for c in (msg.tool_calls or [])]
        print(f"{model:40} {time.perf_counter() - started:5.1f}s  tool_calls={calls}")
    except Exception as err:  # noqa: BLE001
        text = str(err).replace("\n", " ")
        kind = "RATE/QUOTA" if "429" in text or "RESOURCE_EXHAUSTED" in text or "RateLimit" in text else "ERROR"
        print(f"{model:40} {time.perf_counter() - started:5.1f}s  {kind}: {text[:140]}")


async def main() -> None:
    for model in sys.argv[1:]:
        await probe(model)


asyncio.run(main())
