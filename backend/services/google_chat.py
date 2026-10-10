"""Google Chat Service: Handles message delivery, card payloads, DMs, and webhook verification."""

import asyncio
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


CHAT_SERVICE_ACCOUNT = "chat@system.gserviceaccount.com"
CHAT_CERTS_URL = (
    "https://www.googleapis.com/service_accounts/v1/metadata/x509/" + CHAT_SERVICE_ACCOUNT
)
CHAT_SCOPES = ["https://www.googleapis.com/auth/chat.bot"]

_credentials: Optional[service_account.Credentials] = None
_credentials_lock = asyncio.Lock()


def _load_credentials() -> Optional[service_account.Credentials]:
    """Build service-account credentials from env JSON, a key file, or ADC path."""
    json_str = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if json_str and json_str.strip().startswith("{"):
        try:
            return service_account.Credentials.from_service_account_info(
                json.loads(json_str), scopes=CHAT_SCOPES
            )
        except Exception as err:
            logger.warning("Invalid GOOGLE_SERVICE_ACCOUNT_JSON: %s", err)

    for path in (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", ""),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
    ):
        if path and os.path.exists(path):
            try:
                return service_account.Credentials.from_service_account_file(path, scopes=CHAT_SCOPES)
            except Exception as err:
                logger.warning("Could not load service account credentials from %s: %s", path, err)
    return None


def reset_credentials_cache() -> None:
    """Drop cached credentials (used by tests and after config changes)."""
    global _credentials
    _credentials = None


async def get_chat_auth_headers() -> dict[str, str]:
    """Return a Bearer header for the Chat API, refreshing the token only when needed.

    Credential loading and token refresh perform blocking network I/O, so they run
    in a worker thread and the token is cached until it expires.
    """
    global _credentials
    async with _credentials_lock:
        if _credentials is None:
            _credentials = await asyncio.to_thread(_load_credentials)
        if _credentials is None:
            return {}
        if not _credentials.valid:
            try:
                await asyncio.to_thread(_credentials.refresh, GoogleAuthRequest())
            except Exception as err:
                logger.warning("Could not refresh Google Chat access token: %s", err)
                _credentials = None
                return {}
        return {"Authorization": f"Bearer {_credentials.token}"}


def verify_google_chat_bearer_token(
    authorization_header: Optional[str],
    audience: Optional[str] = None,
) -> bool:
    """Validate the Google-signed Bearer token on an incoming Chat request.

    Accepts the two documented modes and nothing else:
    * "HTTP endpoint URL" audience: an OIDC token whose verified email is the
      Chat service account.
    * "Project number" audience: a JWT issued and signed by the Chat service account.

    A configured audience is mandatory; without one any token would pass.
    Reference: https://developers.google.com/workspace/chat/verify-requests-from-chat
    """
    if not settings.GOOGLE_CHAT_VERIFY_AUTH:
        return True  # development / testing mode

    if not authorization_header or not authorization_header.startswith("Bearer "):
        logger.warning("Missing or malformed Authorization Bearer header")
        return False

    aud = audience or settings.GOOGLE_CHAT_AUDIENCE
    if not aud:
        logger.error("GOOGLE_CHAT_VERIFY_AUTH is on but GOOGLE_CHAT_AUDIENCE is not configured")
        return False

    token = authorization_header[7:].strip()
    request = GoogleAuthRequest()

    try:
        info = id_token.verify_oauth2_token(token, request, audience=aud)
    except Exception:
        try:
            info = id_token.verify_token(token, request, audience=aud, certs_url=CHAT_CERTS_URL)
        except Exception as err:
            logger.warning("Google Chat Bearer token verification failed: %s", err)
            return False

    issuer = info.get("iss", "")
    if issuer == CHAT_SERVICE_ACCOUNT:
        return True
    if (
        issuer in ("https://accounts.google.com", "accounts.google.com")
        and info.get("email") == CHAT_SERVICE_ACCOUNT
        and info.get("email_verified") is True
    ):
        return True
    logger.warning("Rejected Google Chat token from unexpected issuer/identity: %s", issuer)
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
    headers = await get_chat_auth_headers()

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
    headers = await get_chat_auth_headers()

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


async def find_dm_space(google_user_id: str) -> Optional[str]:
    """Look up the app's direct-message space with a user.

    The Chat API has no ``users/*/messages`` endpoint: a bot can only post into a
    space, so a proactive DM first needs that user's DM space.
    """
    user_name = google_user_id if google_user_id.startswith("users/") else f"users/{google_user_id}"
    headers = await get_chat_auth_headers()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://chat.googleapis.com/v1/spaces:findDirectMessage",
                params={"name": user_name},
                headers=headers,
            )
        if resp.status_code == 200:
            return resp.json().get("name")
        logger.warning("findDirectMessage for %s returned status %d", user_name, resp.status_code)
    except Exception as err:
        logger.error("Failed to look up DM space for %s: %s", user_name, err)
    return None


async def send_dm(google_user_id: str, text: str, space_id: Optional[str] = None) -> bool:
    """Send a direct message for proactive notifications.

    Uses ``space_id`` (the user's known DM space) when given, otherwise discovers
    it from the Google user id. Returns True only on a successful API response.
    """
    target_space = space_id or await find_dm_space(google_user_id)
    if not target_space:
        return False
    return await send_text_message(target_space, text)
