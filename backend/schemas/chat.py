"""Google Chat event schemas for webhook payloads and card actions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GoogleChatUser(BaseModel):
    """Google Chat user profile payload."""

    name: str = Field(..., description="Google Chat user ID format: users/1234567")
    displayName: Optional[str] = Field(None, description="User's display name")
    email: Optional[str] = Field(None, description="User's email address")
    type: Optional[str] = Field(None, description="HUMAN or BOT")


class GoogleChatSpace(BaseModel):
    """Google Chat space payload."""

    name: str = Field(..., description="Space identifier format: spaces/AAA123")
    type: Optional[str] = Field(None, description="ROOM, DM, or SPACE")
    displayName: Optional[str] = Field(None, description="Space display name")


class GoogleChatMessage(BaseModel):
    """Google Chat message payload."""

    name: Optional[str] = Field(None, description="Message resource name")
    text: str = Field(..., description="Raw text of the user message")
    thread: Optional[Dict[str, Any]] = Field(None, description="Thread info")


class CardAction(BaseModel):
    """Action payload for interactive button clicks."""

    actionMethodName: Optional[str] = Field(None, description="Name of action method, e.g. confirm_delete")
    parameters: Optional[List[Dict[str, str]]] = Field(None, description="Action parameter key-value pairs")


class GoogleChatEvent(BaseModel):
    """Incoming Google Chat webhook event schema."""

    type: str = Field(..., description="MESSAGE, CARD_CLICKED, ADDED_TO_SPACE, REMOVED_FROM_SPACE")
    eventTime: Optional[str] = Field(None, description="ISO timestamp")
    space: GoogleChatSpace = Field(..., description="Space where event occurred")
    user: Optional[GoogleChatUser] = Field(None, description="Sender profile")
    message: Optional[GoogleChatMessage] = Field(None, description="Message details if type is MESSAGE")
    action: Optional[CardAction] = Field(None, description="Action details if type is CARD_CLICKED")
