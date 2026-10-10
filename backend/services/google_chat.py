"""Google Chat Service: Handles message delivery, card payloads, DMs, and webhook verification."""

import hashlib
import hmac
import json
import logging
import os
from typing import Any, Optional
import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token, service_account

from config import settings

logger = logging.getLogger(__name__)


def get_chat_auth_headers() -> dict[str, str]:
    """Obtains OAuth2 Bearer token from configured Google Service Account."""
    scopes = ["https://www.googleapis.com/auth/chat.bot"]

    # 1. Try from JSON string if configured in env
    json_str = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if json_str and json_str.strip().startswith("{"):
        try:
            info = json.loads(json_str)
            creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
            creds.refresh(GoogleAuthRequest())
            return {"Authorization": f"Bearer {creds.token}"}
        except Exception as err:
            logger.warning("Could not refresh Google service account from JSON env: %s", err)

    # 2. Try from credentials file path
    creds_file = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "")
    if creds_file and os.path.exists(creds_file):
        try:
            creds = service_account.Credentials.from_service_account_file(creds_file, scopes=scopes)
            creds.refresh(GoogleAuthRequest())
            return {"Authorization": f"Bearer {creds.token}"}
        except Exception as err:
            logger.warning("Could not refresh Google service account from file: %s", err)

    # 3. Try standard GOOGLE_APPLICATION_CREDENTIALS environment variable
    g_app_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if g_app_creds and os.path.exists(g_app_creds):
        try:
            creds = service_account.Credentials.from_service_account_file(g_app_creds, scopes=scopes)
            creds.refresh(GoogleAuthRequest())
            return {"Authorization": f"Bearer {creds.token}"}
        except Exception as err:
            logger.warning("Could not refresh Google application credentials: %s", err)

    return {}


def verify_google_chat_bearer_token(
    authorization_header: Optional[str],
    audience: Optional[str] = None,
) -> bool:
    """Validates Google-signed OIDC Bearer token from Google Chat incoming requests.
    
    Official Reference: https://developers.google.com/workspace/chat/verify-requests-from-chat
    """
    if not settings.GOOGLE_CHAT_VERIFY_AUTH:
        # Development / testing mode: verification disabled
        return True

    if not authorization_header or not authorization_header.startswith("Bearer "):
        logger.warning("Missing or malformed Authorization Bearer header")
        return False

    token = authorization_header[7:].strip()
    aud = audience or settings.GOOGLE_CHAT_AUDIENCE or None

    try:
        id_info = id_token.verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=aud,
        )
        iss = id_info.get("iss", "")
        if iss not in ("chat@system.gserviceaccount.com", "https://accounts.google.com", "accounts.google.com"):
            logger.warning("Invalid Google Chat token issuer: %s", iss)
            return False
        return True
    except Exception as err:
        logger.warning("Google Chat Bearer token verification failed: %s", err)
        return False


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verifies optional HMAC-SHA256 signature when custom HMAC secret is configured."""
    secret = settings.GOOGLE_CHAT_WEBHOOK_SECRET
    if not secret:
        return True

    if not signature:
        return False

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)


def build_task_card_v2(task_data: dict[str, Any], header_title: str = "ORBIT Task Card") -> dict[str, Any]:
    """Constructs a Google Chat Cards v2 object representing a task."""
    task_id = str(task_data.get("id", ""))
    title = task_data.get("title", "Untitled Task")
    priority = task_data.get("priority", "MEDIUM")
    status = task_data.get("status", "TODO")
    due_date = task_data.get("due_date") or "No deadline"
    assignee = task_data.get("assignee_name") or "Unassigned"

    priority_icons = {
        "CRITICAL": "🔴 Critical",
        "HIGH": "🟠 High",
        "MEDIUM": "🟡 Medium",
        "LOW": "🟢 Low",
    }
    p_label = priority_icons.get(priority, priority)

    return {
        "cardId": f"task-card-{task_id}",
        "card": {
            "header": {
                "title": header_title,
                "subtitle": f"Task #{task_id}",
                "imageType": "CIRCLE",
            },
            "sections": [
                {
                    "header": "Task Details",
                    "widgets": [
                        {"decoratedText": {"topLabel": "Title", "text": f"<b>{title}</b>"}},
                        {"decoratedText": {"topLabel": "Priority", "text": p_label}},
                        {"decoratedText": {"topLabel": "Status", "text": f"`{status}`"}},
                        {"decoratedText": {"topLabel": "Due Date", "text": str(due_date)}},
                        {"decoratedText": {"topLabel": "Assignee", "text": str(assignee)}},
                        {
                            "buttonList": {
                                "buttons": [
                                    {
                                        "text": "Mark Complete",
                                        "onClick": {
                                            "action": {
                                                "function": "complete_task",
                                                "parameters": [{"key": "task_id", "value": task_id}],
                                            }
                                        },
                                    }
                                ]
                            }
                        },
                    ],
                }
            ],
        },
    }


def build_confirmation_card_v2(
    task_id: str,
    task_title: str,
    thread_id: str,
    prompt_text: str,
) -> dict[str, Any]:
    """Constructs a Google Chat Cards v2 confirmation dialog with Confirm and Cancel buttons."""
    return {
        "cardId": f"confirm-dialog-{task_id}",
        "card": {
            "header": {
                "title": "⚠️ Action Confirmation Required",
                "subtitle": "Human-in-the-Loop Safety Check",
                "imageType": "CIRCLE",
            },
            "sections": [
                {
                    "widgets": [
                        {"textParagraph": {"text": prompt_text}},
                        {
                            "buttonList": {
                                "buttons": [
                                    {
                                        "text": "✅ Confirm Deletion",
                                        "onClick": {
                                            "action": {
                                                "function": "confirm_delete_task",
                                                "parameters": [
                                                    {"key": "task_id", "value": str(task_id)},
                                                    {"key": "thread_id", "value": str(thread_id)},
                                                ],
                                            }
                                        },
                                    },
                                    {
                                        "text": "❌ Cancel",
                                        "onClick": {
                                            "action": {
                                                "function": "cancel_action",
                                                "parameters": [
                                                    {"key": "task_id", "value": str(task_id)},
                                                    {"key": "thread_id", "value": str(thread_id)},
                                                ],
                                            }
                                        },
                                    },
                                ]
                            }
                        },
                    ]
                }
            ],
        },
    }


def build_welcome_card_v2() -> dict[str, Any]:
    """Constructs a Google Chat Cards v2 onboarding card."""
    return {
        "cardId": "orbit-welcome-card",
        "card": {
            "header": {
                "title": "👋 Welcome to ORBIT!",
                "subtitle": "Your Multi-Agent AI Task Assistant",
                "imageType": "CIRCLE",
            },
            "sections": [
                {
                    "header": "Supported Capabilities",
                    "widgets": [
                        {"decoratedText": {"topLabel": "Create Tasks", "text": "<i>'Create a high priority task to test auth by Friday'</i>"}},
                        {"decoratedText": {"topLabel": "View Workload", "text": "<i>'Show my pending tasks'</i> or <i>'What are my overdue tasks?'</i>"}},
                        {"decoratedText": {"topLabel": "Daily Focus Plan", "text": "<i>'What should I focus on today?'</i>"}},
                        {"decoratedText": {"topLabel": "Workload Insights", "text": "<i>'Give me workload recommendations'</i>"}},
                        {"decoratedText": {"topLabel": "Task Updates", "text": "<i>'Make it high priority'</i> or <i>'Mark as completed'</i>"}},
                    ],
                }
            ],
        },
    }


async def send_text_message(
    space_id: str,
    text: str,
    thread_id: Optional[str] = None,
) -> bool:
    """Sends a standard text message to a Google Chat space."""
    clean_space = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
    url = f"https://chat.googleapis.com/v1/{clean_space}/messages"
    headers = get_chat_auth_headers()

    payload: dict[str, Any] = {"text": text}
    if thread_id:
        payload["thread"] = {"name": thread_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return True
            logger.warning("Google Chat API error status=%d body=%s", resp.status_code, resp.text)
    except Exception as err:
        logger.error("Failed to send Google Chat message: %s", err)
    return False


async def send_card_message(
    space_id: str,
    card_json: dict[str, Any],
    fallback_text: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> bool:
    """Sends a Google Chat Cards v2 payload to a space."""
    clean_space = space_id if space_id.startswith("spaces/") else f"spaces/{space_id}"
    url = f"https://chat.googleapis.com/v1/{clean_space}/messages"
    headers = get_chat_auth_headers()

    payload: dict[str, Any] = {
        "text": fallback_text or "ORBIT Task Card",
        "cardsV2": [card_json],
    }
    if thread_id:
        payload["thread"] = {"name": thread_id}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code in (200, 201):
                return True
            logger.warning("Google Chat Card API status=%d body=%s", resp.status_code, resp.text)
    except Exception as err:
        logger.error("Failed to send Google Chat card: %s", err)
    return False


async def send_dm(google_user_id: str, text: str) -> bool:
    """Sends a direct message to a specific user for proactive notifications."""
    clean_user = google_user_id if google_user_id.startswith("users/") else f"users/{google_user_id}"
    url = f"https://chat.googleapis.com/v1/{clean_user}/messages"
    headers = get_chat_auth_headers()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"text": text}, headers=headers)
            return resp.status_code in (200, 201)
    except Exception as err:
        logger.error("Failed to send DM to %s: %s", google_user_id, err)
        return False
