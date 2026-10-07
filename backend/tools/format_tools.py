"""
Google Chat Card and Message Formatting Tools
Builds interactive Google Chat Cards v2 and formatted Markdown text summaries.
"""

from typing import Any, Dict, List, Optional


def format_task_card(task: Dict[str, Any]) -> Dict[str, Any]:
    """Format a task dictionary into a Google Chat Card v2 JSON structure."""
    task_id = str(task.get("id", ""))
    title = task.get("title", "Untitled Task")
    priority = task.get("priority", "MEDIUM")
    status = task.get("status", "TODO")
    due_date = str(task.get("due_date", "No due date"))
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
                        "subtitle": f"Priority: {priority} • Status: {status}",
                        "imageType": "CIRCLE",
                    },
                    "sections": [
                        {
                            "header": "Task Details",
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
        prio = t.get("priority", "MEDIUM")
        t_title = t.get("title", "Untitled")
        due = t.get("due_date", "No due date")
        lines.append(f"{i}. {status_icon} *{t_title}* — [{prio}] (Due: {due})")

    return "\n".join(lines)
