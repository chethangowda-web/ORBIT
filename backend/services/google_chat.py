"""Google Chat Service: Handles message delivery, card payloads, DMs, and webhook verification."""

import hashlib
import hmac
import logging
from typing import Any, Optional
import httpx

from config import settings

logger = logging.getLogger(__name__)


import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest


def get_chat_auth_headers() -> dict[str, str]:
    """Obtains OAuth2 Bearer token from configured Google Service Account file."""
    creds_file = getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "")
    if creds_file and os.path.exists(creds_file):
        try:
            scopes = ["https://www.googleapis.com/auth/chat.bot"]
            creds = service_account.Credentials.from_service_account_file(creds_file, scopes=scopes)
            creds.refresh(GoogleAuthRequest())
            return {"Authorization": f"Bearer {creds.token}"}
        except Exception as err:
            logger.warning("Could not refresh Google service account token: %s", err)
    return {}


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verifies Google Chat webhook signature using HMAC-SHA256."""
    secret = settings.GOOGLE_CHAT_WEBHOOK_SECRET
    if not secret:
        # Secret not configured; allow for local dev / testing
        return True

    if not signature:
        return False

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)


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
