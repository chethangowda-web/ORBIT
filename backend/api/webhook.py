"""Google Chat Webhook Router: Processes incoming events, user auto-registration, and agent triggers."""

import logging
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.orchestrator import process_message
from db.models import User
from db.session import async_session_factory
from schemas.chat import GoogleChatEvent, GoogleChatUser
from services.google_chat import (
    send_card_message,
    send_text_message,
    verify_webhook_signature,
)
from tools.base import get_tool_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Google Chat Webhook"])

WELCOME_TEXT = """👋 *Hello! I am ORBIT*, your Multi-Agent AI Task Assistant.

I am here to help you manage tasks right inside Google Chat. You can:
• *Create tasks:* "Create a high priority task for Rahul to test the API by Friday"
• *List tasks:* "Show my pending tasks"
• *Plan day:* "What should I focus on today?"
• *Analytics:* "Give me workload recommendations"

Type *help* anytime to see all commands!
"""


async def get_or_create_google_user(session: AsyncSession, chat_user: GoogleChatUser) -> User:
    """Auto-registers or retrieves Google Chat user in PostgreSQL database."""
    google_id = chat_user.name
    email = chat_user.email or f"{google_id.replace('users/', '')}@orbit.chat"
    display_name = chat_user.displayName or "Google Chat User"

    # 1. Lookup by email or google_id
    query = select(User).where((User.email == email) | (User.google_id == google_id))
    result = await session.execute(query)
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
            await session.commit()
            await session.refresh(user)
        return user

    # 2. Create new employee
    new_user = User(
        email=email,
        display_name=display_name,
        google_id=google_id,
        role="employee",
        is_active=True,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


async def handle_chat_event(event: GoogleChatEvent) -> None:
    """Asynchronous background processor for Google Chat events."""
    if not event.user:
        logger.warning("Event received without user profile")
        return

    space_id = event.space.name

    async with get_tool_session() as session:
        user = await get_or_create_google_user(session, event.user)
        user_id_str = str(user.id)

        if event.type == "ADDED_TO_SPACE":
            await send_text_message(space_id, WELCOME_TEXT)
            return

        if event.type == "MESSAGE" and event.message:
            raw_msg = event.message.text
            agent_state = await process_message(
                user_id=user_id_str,
                space_id=space_id,
                message=raw_msg,
                session=session,
            )

            resp_text = agent_state.get("response", "No response generated.")
            resp_type = agent_state.get("response_type", "text")
            card_data = agent_state.get("card_data")

            if resp_type == "card" and card_data:
                await send_card_message(space_id, card_data, fallback_text=resp_text)
            else:
                await send_text_message(space_id, resp_text)

        elif event.type == "CARD_CLICKED":
            # Handle HITL button click confirmation
            agent_state = await process_message(
                user_id=user_id_str,
                space_id=space_id,
                message="confirm",
                confirmed=True,
                session=session,
            )
            resp_text = agent_state.get("response", "Action confirmed.")
            await send_text_message(space_id, resp_text)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def google_chat_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_signature: Optional[str] = Header(None, alias="X-Goog-Signature"),
) -> dict[str, str]:
    """HTTP Webhook endpoint for receiving Google Chat POST events."""
    body = await request.body()

    if not verify_webhook_signature(body, x_goog_signature or ""):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Google Chat webhook signature",
        )

    try:
        event = GoogleChatEvent.model_validate_json(body)
    except Exception as err:
        logger.error("Failed to parse Google Chat event: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event schema: {err}",
        )

    background_tasks.add_task(handle_chat_event, event)
    return {"status": "accepted", "event_type": event.type}
