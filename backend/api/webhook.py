import json
import logging
import uuid
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

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
from services.card_actions import ACTION_KEY
from services.google_chat import (
    build_confirmation_card_v2,
    build_task_card_v2,
    build_welcome_card_v2,
    send_card_message,
    send_text_message,
    verify_google_chat_bearer_token,
    verify_webhook_signature,
)
from crud.chat_events import claim_event, compute_event_key, finalize_event
from schemas.common import api_response
from tools.base import get_tool_session
from tools.task_tools import complete_task

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
    real_email = (chat_user.email or "").strip().lower()
    email = real_email or f"{google_id.replace('users/', '')}@orbit.chat"
    display_name = chat_user.displayName or "Google Chat User"

    # 1. The Chat identity itself wins. Looking up "email OR google_id" in one query could match
    # two rows (a placeholder account made from an event without an email, plus a real account),
    # which raised MultipleResultsFound for every later message from that person.
    result = await session.execute(select(User).where(User.google_id == google_id))
    user = result.scalars().first()
    if user:
        return user

    # 2. Otherwise match an existing account by email, ignoring case (registration lowercases
    # emails, Chat may not), and link this Chat identity to it.
    if real_email:
        result = await session.execute(select(User).where(func.lower(User.email) == real_email))
        user = result.scalars().first()
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


def _extract_response_text(response_payload: dict[str, Any]) -> str:
    """Extracts a plain-text summary from a formatted Chat response for ledger caching."""
    if "text" in response_payload:
        return str(response_payload["text"])
    try:
        return str(
            response_payload["hostAppDataAction"]["chatDataAction"]["createMessageAction"]["message"].get(
                "text", "Action processed."
            )
        )
    except Exception:
        return "Action processed."


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


# Slash commands. Names work for typed "/tasks"; ids are the numbers entered for each command in
# the Chat app configuration (see docs/GOOGLE_CHAT_SETUP.md), so both routes behave the same.
SLASH_PROMPTS = {
    "help": "help",
    "tasks": "Show my pending tasks",
    "plan": "Plan my day",
    "overdue": "What are my overdue tasks?",
    "insights": "Give me workload recommendations",
}
SLASH_COMMAND_IDS = {"1": "help", "2": "tasks", "3": "plan", "4": "overdue", "5": "new", "6": "insights"}


def expand_slash_command(text: str, command_id: Optional[str] = None, argument: Optional[str] = None) -> str:
    """Turn a slash command into the natural-language request the agents understand.

    Anything that is not a recognised command is returned unchanged, so ordinary text
    that merely starts with "/" still reaches the agent.
    """
    stripped = text.strip()
    name = SLASH_COMMAND_IDS.get(str(command_id)) if command_id is not None else None
    arg = (argument or "").strip()
    if name is None and stripped.startswith("/"):
        head, _, rest = stripped[1:].partition(" ")
        name, arg = head.lower(), arg or rest.strip()
    if name == "new":
        return f"Create a task {arg}" if arg else "help"
    if name in SLASH_PROMPTS:
        return SLASH_PROMPTS[name]
    return text


CONFIRM_ACTIONS = {"confirm_delete_task", "confirm_action"}
CANCEL_ACTIONS = {"cancel_action", "cancel"}
GENERIC_ERROR_TEXT = "ORBIT hit an internal error and could not finish that. Please try again."


def conversation_key(thread: str, user_id: str) -> str:
    """Memory key for one person in one Chat thread.

    Rooms are shared, so keying by thread alone would let "make it high priority" from one
    person resolve to a colleague's task. Cards carry the plain thread; the user is added here.
    """
    return f"{thread}:{user_id}"


def _is_dm(space: GoogleChatSpace) -> bool:
    """True for one-to-one bot conversations."""
    return (
        space.type == "DM"
        or bool(getattr(space, "singleUserBotDm", False))
        or getattr(space, "spaceType", "") == "DIRECT_MESSAGE"
    )


def _card_params(event: GoogleChatEvent) -> dict[str, str]:
    """Flatten card button parameters into a key/value mapping."""
    if not event.action:
        return {}
    return {p.get("key"): p.get("value") for p in (event.action.parameters or []) if p.get("key")}


def _compute_event_key(event: GoogleChatEvent) -> Optional[str]:
    """Stable idempotency key for side-effecting events; None for harmless ones."""
    space_id = event.space.name
    if event.type == "MESSAGE" and event.message:
        return compute_event_key(
            event_type="MESSAGE",
            space_name=space_id,
            user_name=event.user.name,
            event_time=event.eventTime,
            discriminator=event.message.name or f"text:{event.message.text}",
        )
    if event.type == "CARD_CLICKED" and event.action:
        discriminator = f"{event.action.actionMethodName}:{json.dumps(_card_params(event), sort_keys=True)}"
        return compute_event_key(
            event_type="CARD_CLICKED",
            space_name=space_id,
            user_name=event.user.name,
            event_time=event.eventTime,
            discriminator=discriminator,
        )
    return None


def _authenticate_request(body: bytes, authorization: Optional[str], signature: Optional[str]) -> None:
    """Reject requests that fail Google Bearer verification or the optional HMAC check."""
    if settings.GOOGLE_CHAT_VERIFY_AUTH:
        valid_bearer = verify_google_chat_bearer_token(authorization)
        valid_hmac = (
            verify_webhook_signature(body, signature or "")
            if settings.GOOGLE_CHAT_WEBHOOK_SECRET
            else False
        )
        if not (valid_bearer or valid_hmac):
            logger.warning("[WEBHOOK AUTH FAILED] Missing or invalid authorization token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing Google Chat authentication token",
            )
    elif settings.GOOGLE_CHAT_WEBHOOK_SECRET and not verify_webhook_signature(body, signature or ""):
        # A configured secret makes the signature mandatory: omitting the header is not a bypass.
        logger.warning("[WEBHOOK AUTH FAILED] Missing or invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Google Chat webhook signature",
        )


def _message_response(agent_state: dict[str, Any], thread_id: str, is_addon: bool) -> dict[str, Any]:
    """Turn an agent result into a Chat response, using cards where the agent asked for one."""
    text = agent_state.get("response", "No response generated.")
    card_data = agent_state.get("card_data")
    pending = agent_state.get("pending_confirmation") or {}

    if agent_state.get("needs_confirmation") and agent_state.get("referenced_task_id"):
        card = build_confirmation_card_v2(
            task_id=str(agent_state["referenced_task_id"]),
            task_title=pending.get("task_title", "Task"),
            thread_id=thread_id,
            prompt_text=text,
        )
        return format_chat_response(text, cards_v2=[card], is_addon=is_addon)

    if agent_state.get("response_type") == "card" and card_data:
        # Cards that already contain the full content ask for a short companion line.
        if isinstance(card_data, dict) and card_data.get("chat_text"):
            text = card_data["chat_text"]
        if isinstance(card_data, dict) and card_data.get("cardsV2"):
            card = card_data["cardsV2"][0]
        elif isinstance(card_data, dict) and "card" in card_data:
            card = card_data
        else:
            card = build_task_card_v2(card_data)
        return format_chat_response(text, cards_v2=[card], is_addon=is_addon)

    return format_chat_response(text, is_addon=is_addon)


async def _handle_message(
    event: GoogleChatEvent, session: AsyncSession, user_id: str, is_addon: bool
) -> dict[str, Any]:
    """Run a typed chat message through the agent graph."""
    space_id = event.space.name
    thread_name = (event.message.thread or {}).get("name") if event.message.thread else None
    thread_id = space_id if _is_dm(event.space) else (thread_name or space_id)

    slash = event.message.slashCommand or {}
    message = expand_slash_command(
        normalize_chat_message(event.message.text),
        command_id=slash.get("commandId"),
        argument=event.message.argumentText,
    )

    agent_state = await process_message(
        user_id=user_id,
        space_id=space_id,
        message=message,
        thread_id=conversation_key(thread_id, user_id),
        session=session,
    )
    logger.info(
        "[WEBHOOK] message handled intent=%s agent=%s",
        agent_state.get("intent"),
        agent_state.get("active_agent"),
    )
    return _message_response(agent_state, thread_id, is_addon)


async def _handle_card_click(
    event: GoogleChatEvent, session: AsyncSession, user_id: str, is_addon: bool
) -> dict[str, Any]:
    """Translate a card button press into the matching agent action."""
    space_id = event.space.name
    params = _card_params(event)
    # The button's `function` may be the add-on endpoint address; the real name rides in a parameter.
    action = params.get(ACTION_KEY) or event.action.actionMethodName or ""
    thread_id = space_id if _is_dm(event.space) else (params.get("thread_id") or space_id)

    if action in CONFIRM_ACTIONS:
        message, confirmed = "yes", True
    elif action in CANCEL_ACTIONS:
        message, confirmed = "cancel", False
    elif action == "complete_task" and params.get("task_id"):
        # Deterministic: a button press already names the task, so skip language parsing.
        result = await complete_task.ainvoke({"task_id": params["task_id"], "completed_by_id": user_id})
        if result.get("success"):
            title = (result.get("data") or {}).get("title", "Task")
            return format_chat_response(f"🎉 *{title}* marked as completed!", is_addon=is_addon)
        return format_chat_response(f"❌ {result.get('error', 'Could not complete that task.')}", is_addon=is_addon)
    else:
        # Never forward unknown button ids to the agent as free text: a crafted
        # action could otherwise be read as "confirm" against a pending delete.
        logger.warning("[WEBHOOK] Ignoring unsupported card action %r", action)
        return format_chat_response("That action is no longer available.", is_addon=is_addon)

    agent_state = await process_message(
        user_id=user_id,
        space_id=space_id,
        message=message,
        thread_id=conversation_key(thread_id, user_id),
        confirmed=confirmed,
        session=session,
    )
    return format_chat_response(agent_state.get("response", "Action processed."), is_addon=is_addon)


@router.post("/webhook", status_code=status.HTTP_200_OK)
@router.post("", status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/", status_code=status.HTTP_200_OK, include_in_schema=False)
async def google_chat_webhook(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_goog_signature: Optional[str] = Header(None, alias="X-Goog-Signature"),
) -> dict[str, Any]:
    """Receive Google Chat events (Bearer/HMAC verified, idempotent, PII-safe logging)."""
    body = await request.body()
    logger.info("[WEBHOOK INCOMING] %d bytes", len(body))
    if settings.LOG_WEBHOOK_PAYLOADS:
        logger.debug("[WEBHOOK PAYLOAD] %s", body.decode("utf-8", errors="replace"))

    _authenticate_request(body, authorization, x_goog_signature)

    try:
        event = parse_chat_event_payload(body)
    except Exception as err:
        logger.warning("Failed to parse Google Chat event: %s", err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid event schema.",
        )
    logger.info("[WEBHOOK] parsed type=%s space=%s", event.type, event.space.name)

    is_addon = event.commonEventObject is not None

    if event.type in ("APP_HOME", "ADDED_TO_SPACE"):
        if event.user:
            async with get_tool_session() as session:
                await get_or_create_google_user(session, event.user)
        return format_chat_response(
            WELCOME_TEXT, cards_v2=[build_welcome_card_v2()], is_addon=is_addon, is_app_home=True
        )

    if not event.user:
        return format_chat_response("Event received without user profile.", is_addon=is_addon)

    # Idempotency: a redelivered message or button click must never re-run its tools.
    event_key = _compute_event_key(event)
    if event_key:
        is_duplicate, cached_response = await claim_event(event_key, event.type)
        if is_duplicate:
            logger.info("[WEBHOOK DEDUP] Duplicate event ignored")
            return format_chat_response(
                cached_response or "This action was already processed.", is_addon=is_addon
            )

    result = format_chat_response("Action processed.", is_addon=is_addon)
    failed = False
    try:
        async with get_tool_session() as session:
            user = await get_or_create_google_user(session, event.user)
            if _is_dm(event.space) and user.google_space_id != event.space.name:
                # Remember the verified DM space so proactive messages can reach this user.
                user.google_space_id = event.space.name
                await session.commit()
            if event.type == "MESSAGE" and event.message:
                result = await _handle_message(event, session, str(user.id), is_addon)
            elif event.type == "CARD_CLICKED" and event.action:
                result = await _handle_card_click(event, session, str(user.id), is_addon)
    except Exception:
        error_id = uuid.uuid4().hex[:12]
        logger.exception("[WEBHOOK PROCESSING ERROR] ref=%s", error_id)
        failed = True
        result = format_chat_response(f"{GENERIC_ERROR_TEXT} (ref {error_id})", is_addon=is_addon)

    if event_key:
        await finalize_event(
            event_key,
            response_text=_extract_response_text(result),
            status="FAILED" if failed else "COMPLETED",
        )
    return result


SUGGESTED_ACTIONS_BY_INTENT = {
    "PLAN_DAY": [
        "Show my pending tasks",
        "What are my overdue tasks?",
        "Create a new task",
    ],
    "CREATE_TASK": [
        "Plan my day",
        "Show my pending tasks",
        "Undo that",
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
            classifier=trace_meta.get("classifier"),
            steps=trace_meta.get("steps") or [],
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
