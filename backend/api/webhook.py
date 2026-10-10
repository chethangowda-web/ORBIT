import json
import logging
import uuid
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agents.orchestrator import process_message
from crud.tasks import get_task
from db.models import User
from db.session import async_session_factory, get_db
from dependencies import get_current_user
from schemas.chat import (
    CardAction,
    ChatExecutionMetadata,
    ChatQueryRequest,
    ChatQueryResponse,
    GoogleChatEvent,
    GoogleChatMessage,
    GoogleChatSpace,
    GoogleChatUser,
    ReferencedTaskSummary,
)
import re
from config import settings
from services.google_chat import (
    build_confirmation_card_v2,
    build_task_card_v2,
    build_welcome_card_v2,
    send_card_message,
    send_text_message,
    verify_google_chat_bearer_token,
    verify_webhook_signature,
)
from schemas.common import api_response
from tools.base import get_tool_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat & Google Webhook"])

WELCOME_TEXT = """👋 *Hello! I am ORBIT*, your Multi-Agent AI Task Assistant.

I am here to help you manage tasks right inside Google Chat. You can:
• *Create tasks:* "Create a high priority task for Rahul to test the API by Friday"
• *List tasks:* "Show my pending tasks"
• *Plan day:* "What should I focus on today?"
• *Analytics:* "Give me workload recommendations"

Type *help* anytime to see all commands!
"""


def normalize_chat_message(text: str) -> str:
    """Strip Google Chat bot user mentions (e.g. <users/123456789> or @ORBIT) and wrapping quotes."""
    clean = re.sub(r"<users\/[^>]+>", "", text)
    clean = re.sub(r"(?i)^@ORBIT\b", "", clean.strip()).strip()
    if (clean.startswith('"') and clean.endswith('"')) or (clean.startswith("'") and clean.endswith("'")):
        clean = clean[1:-1].strip()
    return clean or text.strip()



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
            welcome_card = build_welcome_card_v2()
            await send_card_message(space_id, welcome_card, fallback_text=WELCOME_TEXT)
            return

        if event.type == "MESSAGE" and event.message:
            raw_msg = normalize_chat_message(event.message.text)
            thread_name = (event.message.thread or {}).get("name") if event.message.thread else None
            is_dm = event.space.type == "DM" or getattr(event.space, "singleUserBotDm", False) or getattr(event.space, "spaceType", "") == "DIRECT_MESSAGE"
            effective_thread_id = space_id if is_dm else (thread_name or space_id)

            agent_state = await process_message(
                user_id=user_id_str,
                space_id=space_id,
                message=raw_msg,
                thread_id=effective_thread_id,
                session=session,
            )

            resp_text = agent_state.get("response", "No response generated.")
            resp_type = agent_state.get("response_type", "text")
            card_data = agent_state.get("card_data")
            needs_conf = agent_state.get("needs_confirmation", False)

            if needs_conf and agent_state.get("referenced_task_id"):
                ref_id = str(agent_state.get("referenced_task_id"))
                conf_card = build_confirmation_card_v2(
                    task_id=ref_id,
                    task_title="Task",
                    thread_id=thread_name or space_id,
                    prompt_text=resp_text,
                )
                await send_card_message(space_id, conf_card, fallback_text=resp_text, thread_id=thread_name)
            elif resp_type == "card" and card_data:
                if isinstance(card_data, dict) and "cardsV2" in card_data and card_data["cardsV2"]:
                    card_v2 = card_data["cardsV2"][0]
                elif isinstance(card_data, dict) and "card" in card_data:
                    card_v2 = card_data
                else:
                    card_v2 = build_task_card_v2(card_data)
                await send_card_message(space_id, card_v2, fallback_text=resp_text, thread_id=thread_name)
            else:
                await send_text_message(space_id, resp_text, thread_id=thread_name)

        elif event.type == "CARD_CLICKED" and event.action:
            # Handle interactive card button clicks (Confirm / Cancel / Complete)
            action_name = event.action.actionMethodName or ""
            params = {p.get("key"): p.get("value") for p in (event.action.parameters or []) if p.get("key")}
            task_id = params.get("task_id", "")
            target_thread = params.get("thread_id") or space_id

            if action_name in ("confirm_delete_task", "confirm_action"):
                agent_state = await process_message(
                    user_id=user_id_str,
                    space_id=space_id,
                    message="yes",
                    thread_id=target_thread,
                    confirmed=True,
                    session=session,
                )
            elif action_name in ("cancel_action", "cancel"):
                agent_state = await process_message(
                    user_id=user_id_str,
                    space_id=space_id,
                    message="cancel",
                    thread_id=target_thread,
                    confirmed=False,
                    session=session,
                )
            elif action_name == "complete_task" and task_id:
                agent_state = await process_message(
                    user_id=user_id_str,
                    space_id=space_id,
                    message=f"Mark Task #{task_id} as completed",
                    thread_id=target_thread,
                    session=session,
                )
            else:
                agent_state = await process_message(
                    user_id=user_id_str,
                    space_id=space_id,
                    message=action_name or "confirm",
                    thread_id=target_thread,
                    session=session,
                )

            resp_text = agent_state.get("response", "Action processed.")
            await send_text_message(space_id, resp_text, thread_id=target_thread)


def format_chat_response(
    text: str,
    cards_v2: Optional[list] = None,
    is_addon: bool = False,
    is_app_home: bool = False,
) -> dict[str, Any]:
    """Formats response strictly for Google Workspace Add-ons (DataActions/RenderActions) or standard Chat."""
    msg: dict[str, Any] = {"text": text}
    if cards_v2:
        msg["cardsV2"] = cards_v2

    if is_addon:
        if is_app_home and cards_v2 and len(cards_v2) > 0:
            card_obj = cards_v2[0].get("card") if isinstance(cards_v2[0], dict) and "card" in cards_v2[0] else cards_v2[0]
            return {
                "renderActions": {
                    "action": {
                        "navigations": [
                            {
                                "pushCard": card_obj
                            }
                        ]
                    }
                }
            }
        return {
            "hostAppDataAction": {
                "chatDataAction": {
                    "createMessageAction": {
                        "message": msg
                    }
                }
            }
        }

    return msg


def parse_chat_event_payload(body_bytes: bytes) -> GoogleChatEvent:
    """Parses and normalizes both standard Google Chat events and Workspace Add-on commonEventObject payloads."""
    raw = json.loads(body_bytes.decode("utf-8") or "{}")
    chat_data = raw.get("chat", {}) if isinstance(raw.get("chat"), dict) else {}
    msg_payload = chat_data.get("messagePayload", {}) if isinstance(chat_data.get("messagePayload"), dict) else {}

    # Extract message from standard or Workspace Add-on location
    msg_raw = raw.get("message") or chat_data.get("message") or msg_payload.get("message")

    # Extract space
    space_raw = (
        raw.get("space")
        or chat_data.get("space")
        or msg_payload.get("space")
        or (msg_raw.get("space") if isinstance(msg_raw, dict) else None)
        or {"name": "spaces/default", "type": "DM"}
    )
    if isinstance(space_raw, str):
        space_raw = {"name": space_raw, "type": "DM"}

    # Extract user
    user_raw = (
        raw.get("user")
        or chat_data.get("user")
        or (msg_raw.get("sender") if isinstance(msg_raw, dict) else None)
    )

    # Extract action
    action_raw = raw.get("action")
    if not action_raw and "commonEventObject" in raw:
        ceo = raw.get("commonEventObject", {})
        ceo_params = ceo.get("parameters", {})
        if ceo_params:
            action_raw = {
                "actionMethodName": ceo.get("invokedFunction", "card_action"),
                "parameters": (
                    [{"key": k, "value": str(v)} for k, v in ceo_params.items()]
                    if isinstance(ceo_params, dict)
                    else ceo_params
                ),
            }

    # Determine event type
    event_type = raw.get("type")
    if not event_type:
        if msg_raw:
            event_type = "MESSAGE"
        elif action_raw or raw.get("commonEventObject", {}).get("parameters") or chat_data.get("buttonClickedPayload"):
            event_type = "CARD_CLICKED"
        elif "commonEventObject" in raw and not msg_raw:
            event_type = "APP_HOME"
        else:
            event_type = "MESSAGE"

    return GoogleChatEvent(
        type=event_type,
        eventTime=raw.get("eventTime") or chat_data.get("eventTime"),
        space=GoogleChatSpace.model_validate(space_raw) if isinstance(space_raw, dict) else GoogleChatSpace(name=str(space_raw)),
        user=GoogleChatUser.model_validate(user_raw) if isinstance(user_raw, dict) else None,
        message=GoogleChatMessage.model_validate(msg_raw) if isinstance(msg_raw, dict) else None,
        action=CardAction.model_validate(action_raw) if isinstance(action_raw, dict) else None,
        commonEventObject=raw.get("commonEventObject"),
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
@router.post("", status_code=status.HTTP_200_OK)
@router.post("/", status_code=status.HTTP_200_OK)
async def google_chat_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_goog_signature: Optional[str] = Header(None, alias="X-Goog-Signature"),
) -> dict[str, Any]:
    """HTTP Webhook endpoint for receiving Google Chat POST events with Bearer & signature verification."""
    body = await request.body()
    logger.info("[WEBHOOK INCOMING] Payload size: %d bytes | Raw: %s", len(body), body.decode("utf-8", errors="replace"))

    # 1. Enforce Google native Bearer verification if configured
    if settings.GOOGLE_CHAT_VERIFY_AUTH:
        is_valid_bearer = verify_google_chat_bearer_token(authorization)
        is_valid_hmac = verify_webhook_signature(body, x_goog_signature or "") if settings.GOOGLE_CHAT_WEBHOOK_SECRET else False
        if not (is_valid_bearer or is_valid_hmac):
            logger.warning("[WEBHOOK AUTH FAILED] Missing or invalid authorization token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing Google Chat authentication token",
            )
    elif settings.GOOGLE_CHAT_WEBHOOK_SECRET and x_goog_signature:
        if not verify_webhook_signature(body, x_goog_signature):
            logger.warning("[WEBHOOK AUTH FAILED] Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Google Chat webhook signature",
            )

    try:
        event = parse_chat_event_payload(body)
        logger.info("[WEBHOOK] Parsed event: type=%s user=%s space=%s message=%s",
                    event.type,
                    event.user.displayName if event.user else "None",
                    event.space.name,
                    event.message.text if event.message else "None")
    except Exception as err:
        logger.exception("Failed to parse Google Chat event: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid event schema: {err}",
        )

    is_addon = bool(event.commonEventObject is not None)

    # 1. App Home & Added to Space onboarding
    if event.type in ("APP_HOME", "ADDED_TO_SPACE"):
        if event.user:
            async with get_tool_session() as session:
                await get_or_create_google_user(session, event.user)
        welcome_card = build_welcome_card_v2()
        response = format_chat_response(WELCOME_TEXT, cards_v2=[welcome_card], is_addon=is_addon, is_app_home=True)
        logger.info("[WEBHOOK OUTGOING] Responding to %s with welcome card", event.type)
        return response

    if not event.user:
        return format_chat_response("Event received without user profile.", is_addon=is_addon)

    space_id = event.space.name
    try:
        async with get_tool_session() as session:
            user = await get_or_create_google_user(session, event.user)
            user_id_str = str(user.id)

            is_dm = event.space.type == "DM" or getattr(event.space, "singleUserBotDm", False) or getattr(event.space, "spaceType", "") == "DIRECT_MESSAGE"

            if event.type == "MESSAGE" and event.message:
                raw_msg = normalize_chat_message(event.message.text)
                thread_name = (event.message.thread or {}).get("name") if event.message.thread else None
                effective_thread_id = space_id if is_dm else (thread_name or space_id)

                agent_state = await process_message(
                    user_id=user_id_str,
                    space_id=space_id,
                    message=raw_msg,
                    thread_id=effective_thread_id,
                    session=session,
                )

                resp_text = agent_state.get("response", "No response generated.")
                resp_type = agent_state.get("response_type", "text")
                card_data = agent_state.get("card_data")
                needs_conf = agent_state.get("needs_confirmation", False)

                logger.info("[WEBHOOK OUTGOING] Agent response preview: type=%s text=%r", resp_type, resp_text[:80])

                if needs_conf and agent_state.get("referenced_task_id"):
                    ref_id = str(agent_state.get("referenced_task_id"))
                    conf_card = build_confirmation_card_v2(
                        task_id=ref_id,
                        task_title="Task",
                        thread_id=effective_thread_id,
                        prompt_text=resp_text,
                    )
                    return format_chat_response(resp_text, cards_v2=[conf_card], is_addon=is_addon)
                elif resp_type == "card" and card_data:
                    if isinstance(card_data, dict) and "cardsV2" in card_data and card_data["cardsV2"]:
                        card_v2 = card_data["cardsV2"][0]
                    elif isinstance(card_data, dict) and "card" in card_data:
                        card_v2 = card_data
                    else:
                        card_v2 = build_task_card_v2(card_data)
                    return format_chat_response(resp_text, cards_v2=[card_v2], is_addon=is_addon)
                else:
                    return format_chat_response(resp_text, is_addon=is_addon)

            elif event.type == "CARD_CLICKED" and event.action:
                action_name = event.action.actionMethodName or ""
                params = {p.get("key"): p.get("value") for p in (event.action.parameters or []) if p.get("key")}
                task_id = params.get("task_id", "")
                target_thread = space_id if is_dm else (params.get("thread_id") or space_id)

                if action_name in ("confirm_delete_task", "confirm_action"):
                    agent_state = await process_message(
                        user_id=user_id_str,
                        space_id=space_id,
                        message="yes",
                        thread_id=target_thread,
                        confirmed=True,
                        session=session,
                    )
                elif action_name in ("cancel_action", "cancel"):
                    agent_state = await process_message(
                        user_id=user_id_str,
                        space_id=space_id,
                        message="cancel",
                        thread_id=target_thread,
                        confirmed=False,
                        session=session,
                    )
                elif action_name == "complete_task" and task_id:
                    agent_state = await process_message(
                        user_id=user_id_str,
                        space_id=space_id,
                        message=f"Mark Task #{task_id} as completed",
                        thread_id=target_thread,
                        session=session,
                    )
                else:
                    agent_state = await process_message(
                        user_id=user_id_str,
                        space_id=space_id,
                        message=action_name or "confirm",
                        thread_id=target_thread,
                        session=session,
                    )

                resp_text = agent_state.get("response", "Action processed.")
                logger.info("[WEBHOOK OUTGOING] Card click response: %r", resp_text[:80])
                return format_chat_response(resp_text, is_addon=is_addon)
    except Exception as exc:
        logger.exception("[WEBHOOK PROCESSING ERROR] %s", exc)
        return format_chat_response(f"⚠️ ORBIT encountered an internal error: {str(exc)}", is_addon=is_addon)

    return format_chat_response("Action processed.", is_addon=is_addon)


SUGGESTED_ACTIONS_BY_INTENT = {
    "PLAN_DAY": [
        "Show my pending tasks",
        "What are my overdue tasks?",
        "Create a new task",
    ],
    "CREATE_TASK": [
        "Plan my day",
        "Show my pending tasks",
        "View task details",
    ],
    "GET_MY_TASKS": [
        "Plan my day",
        "Show my overdue tasks",
        "What should I focus on today?",
    ],
    "GET_OVERDUE_TASKS": [
        "Plan my day",
        "Show my pending tasks",
        "Mark the top task as completed",
    ],
    "COMPLETE_TASK": [
        "Show my pending tasks",
        "Plan my day",
    ],
    "GET_RECOMMENDATIONS": [
        "Plan my day",
        "Show my overdue tasks",
    ],
}
DEFAULT_SUGGESTED_ACTIONS = [
    "Plan my day",
    "Show my pending tasks",
    "What are my overdue tasks?",
]


@router.post("/query", status_code=status.HTTP_200_OK)
async def chat_query(
    payload: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Authenticated endpoint for natural language interactions via the Web Command Center."""
    user_id_str = str(current_user.id)
    space_id = current_user.google_space_id or f"web_{user_id_str}"

    # Strict user thread isolation: scope the thread key to the authenticated user ID
    client_thread = payload.thread_id.strip() if payload.thread_id else "default"
    isolated_thread_id = f"user_{user_id_str}:{client_thread}"

    agent_state = await process_message(
        user_id=user_id_str,
        space_id=space_id,
        message=payload.message,
        thread_id=isolated_thread_id,
        confirmed=payload.confirmed,
        session=db,
    )

    resp_text = agent_state.get("response") or "I processed your request."
    intent = agent_state.get("intent") or "UNKNOWN"
    active_agent = agent_state.get("active_agent") or "supervisor"
    needs_confirmation = bool(agent_state.get("needs_confirmation", False))
    ref_task_id = agent_state.get("referenced_task_id")

    if needs_confirmation:
        suggested_actions = ["Confirm", "Cancel"]
    else:
        suggested_actions = SUGGESTED_ACTIONS_BY_INTENT.get(intent, DEFAULT_SUGGESTED_ACTIONS)

    referenced_tasks: list[dict[str, Any]] = []
    if ref_task_id:
        try:
            task_uuid = uuid.UUID(ref_task_id)
            task_obj = await get_task(db, task_uuid)
            if task_obj:
                referenced_tasks.append({
                    "id": str(task_obj.id),
                    "title": task_obj.title,
                    "status": task_obj.status,
                    "priority": task_obj.priority,
                    "due_date": str(task_obj.due_date) if task_obj.due_date else None,
                    "assignee_name": task_obj.assignee.display_name if task_obj.assignee else None,
                })
        except Exception:
            pass

    card_data = agent_state.get("card_data")
    if isinstance(card_data, dict) and card_data.get("id"):
        card_id = str(card_data.get("id"))
        if not any(t["id"] == card_id for t in referenced_tasks):
            referenced_tasks.append({
                "id": card_id,
                "title": card_data.get("title", "Task"),
                "status": card_data.get("status"),
                "priority": card_data.get("priority"),
                "due_date": str(card_data.get("due_date")) if card_data.get("due_date") else None,
                "assignee_name": card_data.get("assignee_name"),
            })

    trace_meta = agent_state.get("trace_metadata") or {}

    response_payload = ChatQueryResponse(
        response=resp_text,
        thread_id=client_thread,
        message_id=str(uuid.uuid4()),
        needs_confirmation=needs_confirmation,
        referenced_task_id=str(ref_task_id) if ref_task_id else None,
        referenced_tasks=[ReferencedTaskSummary(**t) for t in referenced_tasks],
        suggested_actions=suggested_actions,
        metadata=ChatExecutionMetadata(
            request_id=trace_meta.get("request_id"),
            active_agent=active_agent,
            agents_invoked=agent_state.get("agents_invoked", [active_agent]),
            intent=intent,
            confidence=agent_state.get("confidence"),
            tool_calls_made=agent_state.get("tool_calls_made", []),
            node_durations_ms=agent_state.get("node_durations_ms", {}),
            total_duration_ms=trace_meta.get("total_duration_ms", 0.0),
            status=trace_meta.get("status", "NEEDS_CONFIRMATION" if needs_confirmation else "SUCCESS"),
        ),
    )

    return api_response(data=response_payload.model_dump())


@router.get("/traces", status_code=status.HTTP_200_OK)
async def list_chat_traces(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve execution traces scoped strictly to the authenticated user."""
    from crud.traces import list_user_traces
    from schemas.trace import AgentExecutionTraceRead

    traces, total = await list_user_traces(db, current_user.id, limit=limit, offset=offset)
    items = [AgentExecutionTraceRead.model_validate(t).model_dump() for t in traces]
    return api_response(data={"items": items, "total": total})


@router.get("/traces/{trace_id}", status_code=status.HTTP_200_OK)
async def get_chat_trace_detail(
    trace_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve details for a specific trace, rejecting cross-user access."""
    from crud.traces import get_user_trace
    from schemas.trace import AgentExecutionTraceRead

    trace = await get_user_trace(db, current_user.id, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution trace not found or access denied.",
        )
    return api_response(data=AgentExecutionTraceRead.model_validate(trace).model_dump())
