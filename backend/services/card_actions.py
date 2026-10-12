"""Button actions for Google Chat cards.

A Chat app that is a Workspace add-on must give each button a full https address as its `function`; Google
calls that address and reports it back as `invokedFunction`. A bare name such as "complete_task" is not
callable, which is why such a button fails with "ORBIT is unable to process your request". So the address
goes in `function` and the real action name travels as a parameter.
"""

from typing import Any, Optional

from config import settings

ACTION_KEY = "orbit_action"


def card_action(name: str, parameters: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    endpoint = (settings.GOOGLE_CHAT_AUDIENCE or "").strip()
    function = endpoint if endpoint.startswith("https://") else name
    return {"function": function, "parameters": [{"key": ACTION_KEY, "value": name}, *(parameters or [])]}
