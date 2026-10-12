"""
Google Chat Card and Message Formatting Tools
Builds interactive Google Chat Cards v2 and formatted Markdown text summaries.
"""

from typing import Any, Dict, List, Optional

from services.card_actions import card_action
from services.wording import due_phrase, friendly  # noqa: F401  (re-exported for the agents)


QUICK_REPLIES = (
    "Show my tasks",
    "Plan my day",
    "Plan my week",
    "What is overdue?",
    "Undo that",
)


def task_summary_line(task: Dict[str, Any]) -> str:
    """One short line under a task title: "High priority · due Friday · with Sarah"."""
    bits = [f"{friendly(task.get('priority', 'MEDIUM'))} priority", due_phrase(task.get("due_date"))]
    assignee = task.get("assignee")
    name = assignee.get("display_name") if isinstance(assignee, dict) else assignee
    if name:
        bits.append(f"with {name}")
    return " · ".join(bits)


def _task_buttons(task_id: str, status: str) -> List[Dict[str, Any]]:
    """The one-tap actions under a task: finish, start, push to tomorrow, undo."""
    status = status.split(".")[-1].upper()
    params = [{"key": "task_id", "value": task_id}]
    buttons: List[Dict[str, Any]] = []
    if status != "DONE":
        buttons.append({"text": "Done", "onClick": {"action": card_action("complete_task", params)}})
        if status == "TODO":
            buttons.append({"text": "Start", "onClick": {"action": card_action("start_task", params)}})
        buttons.append({"text": "Due tomorrow", "onClick": {"action": card_action("snooze_task", params)}})
    buttons.append({"text": "Undo", "onClick": {"action": card_action("undo_last", [])}})
    return buttons


def quick_reply_section(texts: List[str], thread_id: str = "") -> Dict[str, Any]:
    """A row of suggested next messages. Pressing one sends that exact (allow-listed) text as the user."""
    params_extra = [{"key": "thread_id", "value": thread_id}] if thread_id else []
    return {
        "widgets": [
            {
                "buttonList": {
                    "buttons": [
                        {
                            "text": text,
                            "onClick": {"action": card_action("quick_reply", [{"key": "text", "value": text}, *params_extra])},
                        }
                        for text in texts
                        if text in QUICK_REPLIES
                    ]
                }
            }
        ]
    }


def format_task_card(task: Dict[str, Any]) -> Dict[str, Any]:
    """Format a task dictionary into a Google Chat Card v2 JSON structure."""
    task_id = str(task.get("id", ""))
    title = task.get("title", "Untitled Task")
    priority = friendly(task.get("priority", "MEDIUM"))
    status = friendly(task.get("status", "TODO"))
    due_date = due_phrase(task.get("due_date")).capitalize()
    tags = task.get("tags", [])
    tags_str = ", ".join(tags) if tags else "None"

    assignee = task.get("assignee")
    assignee_name = "Unassigned"
    if isinstance(assignee, dict):
        assignee_name = assignee.get("display_name", assignee.get("email", "Assigned"))
    elif assignee:
        assignee_name = str(assignee)

    return {
        "cardsV2": [
            {
                "cardId": f"task-card-{task_id}",
                "card": {
                    "header": {
                        "title": title,
                        "subtitle": f"{priority} priority • {status}",
                        "imageType": "CIRCLE",
                    },
                    "sections": [
                        {
                            "header": "Details",
                            "widgets": [
                                {
                                    "decoratedText": {
                                        "topLabel": "Assignee",
                                        "text": assignee_name,
                                        "startIcon": {"knownIcon": "MEMBERSHIP"},
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "topLabel": "Due Date",
                                        "text": due_date,
                                        "startIcon": {"knownIcon": "CLOCK"},
                                    }
                                },
                                {
                                    "decoratedText": {
                                        "topLabel": "Tags",
                                        "text": tags_str,
                                        "startIcon": {"knownIcon": "BOOKMARK"},
                                    }
                                },
                            ],
                        },
                        {"widgets": [{"buttonList": {"buttons": _task_buttons(task_id, str(task.get("status", "TODO")))}}]},
                    ],
                },
            }
        ]
    }


def format_task_list_text(tasks: List[Dict[str, Any]], title: str = "Tasks") -> str:
    """Format a list of tasks into markdown message text for chat notifications."""
    if not tasks:
        return f"📋 *{title}*\nNo tasks found."

    lines = [f"📋 *{title}* ({len(tasks)} items):"]
    for i, t in enumerate(tasks, 1):
        status_icon = "✅" if t.get("status") == "DONE" else "⏳" if t.get("status") == "IN_PROGRESS" else "⬜"
        prio = friendly(t.get("priority", "MEDIUM"))
        t_title = t.get("title", "Untitled")
        lines.append(f"{i}. {status_icon} *{t_title}*: {prio} priority, {due_phrase(t.get('due_date'))}")

    return "\n".join(lines)


MAX_CARD_TASKS = 8


def format_task_list_card(tasks: List[Dict[str, Any]], title: str = "Tasks") -> Dict[str, Any]:
    """Google Chat Card v2 listing tasks, each open one with one-tap Done (and Start, while it is still to do) buttons.

    The returned dict also carries ``chat_text``: the short line to send alongside the card
    (the full list is already in the card).
    """
    shown = tasks[:MAX_CARD_TASKS]
    widgets: List[Dict[str, Any]] = []
    for t in shown:
        task_id = str(t.get("id", ""))
        priority = friendly(t.get("priority", "MEDIUM"))
        status = friendly(t.get("status", "TODO"))
        due = due_phrase(t.get("due_date"))
        row: Dict[str, Any] = {
            "decoratedText": {
                "text": f"<b>{t.get('title', 'Untitled')}</b>",
                "bottomLabel": f"{priority} priority · {status} · {due}",
                "wrapText": True,
            }
        }
        widgets.append(row)
        raw_status = str(t.get("status") or "TODO").split(".")[-1].upper()
        if raw_status != "DONE":
            params = [{"key": "task_id", "value": task_id}]
            buttons = [{"text": "Done", "onClick": {"action": card_action("complete_task", params)}}]
            if raw_status == "TODO":
                buttons.append({"text": "Start", "onClick": {"action": card_action("start_task", params)}})
            widgets.append({"buttonList": {"buttons": buttons}})
    if len(tasks) > len(shown):
        widgets.append({"textParagraph": {"text": f"<i>and {len(tasks) - len(shown)} more in the ORBIT dashboard</i>"}})

    return {
        "cardsV2": [
            {
                "cardId": "task-list-card",
                "card": {
                    "header": {"title": title, "subtitle": f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}"},
                    "sections": [{"widgets": widgets}],
                },
            }
        ],
        "chat_text": f"📋 *{title}* ({len(tasks)})",
    }
