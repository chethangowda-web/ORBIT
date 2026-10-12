"""
Google Chat Card and Message Formatting Tools
Builds interactive Google Chat Cards v2 and formatted Markdown text summaries.
"""

from typing import Any, Dict, List, Optional

from services.wording import friendly  # noqa: F401  (re-exported for the agents)


def format_task_card(task: Dict[str, Any]) -> Dict[str, Any]:
    """Format a task dictionary into a Google Chat Card v2 JSON structure."""
    task_id = str(task.get("id", ""))
    title = task.get("title", "Untitled Task")
    priority = friendly(task.get("priority", "MEDIUM"))
    status = friendly(task.get("status", "TODO"))
    due_date = str(task.get("due_date") or "No due date")
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
                        }
                    ],
                    "fixedFooter": {
                        "primaryButton": {
                            "text": "Mark Complete",
                            "color": {"red": 0.1, "green": 0.7, "blue": 0.3, "alpha": 1.0},
                            "onClick": {
                                "action": {
                                    "function": "complete_task",
                                    "parameters": [{"key": "task_id", "value": task_id}],
                                }
                            },
                        }
                    },
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
        due = t.get("due_date") or "no due date"
        lines.append(f"{i}. {status_icon} *{t_title}*: {prio} priority, due {due}")

    return "\n".join(lines)


MAX_CARD_TASKS = 8


def format_task_list_card(tasks: List[Dict[str, Any]], title: str = "Tasks") -> Dict[str, Any]:
    """Google Chat Card v2 listing tasks, each with a one-click Complete button.

    The returned dict also carries ``chat_text``: the short line to send alongside the card
    (the full list is already in the card).
    """
    shown = tasks[:MAX_CARD_TASKS]
    widgets: List[Dict[str, Any]] = []
    for t in shown:
        task_id = str(t.get("id", ""))
        priority = friendly(t.get("priority", "MEDIUM"))
        status = friendly(t.get("status", "TODO"))
        due = t.get("due_date") or "no due date"
        row: Dict[str, Any] = {
            "decoratedText": {
                "text": f"<b>{t.get('title', 'Untitled')}</b>",
                "bottomLabel": f"{priority} priority · {status} · due {due}",
                "wrapText": True,
            }
        }
        if status.lower() != "done" and t.get("status") != "DONE":
            row["decoratedText"]["button"] = {
                "text": "Done",
                "onClick": {
                    "action": {
                        "function": "complete_task",
                        "parameters": [{"key": "task_id", "value": task_id}],
                    }
                },
            }
        widgets.append(row)
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
