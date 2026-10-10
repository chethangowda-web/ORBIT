# ARCHITECTURE.md — System Architecture
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.1.0  
**Last Updated:** 2026-10-10

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     COMMUNICATION LAYER                          │
│  ┌─────────────────┐          ┌──────────────────────────────┐  │
│  │  Google Chat Bot│          │    Next.js Web Dashboard      │  │
│  │  (Webhook)      │          │    (REST API consumer)        │  │
│  └────────┬────────┘          └──────────────┬───────────────┘  │
└───────────┼───────────────────────────────────┼─────────────────┘
            │ HTTPS POST                         │ REST API
            ▼                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API GATEWAY (FastAPI)                        │
│  Auth (JWT) │ Rate Limiting (Redis) │ CORS │ Request Validation  │
└─────────────────────────┬───────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
            ▼                           ▼
┌──────────────────────┐    ┌──────────────────────────────────────┐
│  WEBHOOK HANDLER     │    │      REST TASK API                   │
│  /api/chat/webhook   │    │  /api/tasks  /api/users  /api/stats  │
└──────────┬───────────┘    └──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│              MULTI-AGENT ORCHESTRATION (LangGraph)               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SUPERVISOR / ROUTER AGENT                   │    │
│  │  - Classifies intent from natural language               │    │
│  │  - Routes to appropriate specialist agent                │    │
│  │  - Manages conversation state (Redis checkpointer)       │    │
│  └──┬──────────┬─────────────┬────────────┬────────────────┘    │
│     │          │             │            │                       │
│     ▼          ▼             ▼            ▼                       │
│  ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐              │
│  │TASK  │ │PLANNER │ │RECOMMEND │ │REVIEW &      │              │
│  │AGENT │ │AGENT   │ │AGENT     │ │VALIDATION    │              │
│  │      │ │        │ │          │ │AGENT         │              │
│  └──┬───┘ └───┬────┘ └────┬─────┘ └──────┬───────┘              │
│     │         │           │              │                        │
│     └─────────┴───────────┴──────────────┘                       │
│                           │                                       │
│                    MEMORY AGENT                                   │
│              (Cross-agent shared context)                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
    ┌──────────────┐ ┌──────────┐ ┌──────────────────┐
    │  PostgreSQL  │ │  Redis   │ │  LLM PROVIDER    │
    │  (Tasks, DB) │ │  (Cache) │ │  GATEWAY         │
    └──────────────┘ └──────────┘ │  (Google Gemini) │
                                  └──────────────────┘

    ┌──────────────────────────────────────────────────┐
    │           AUTONOMOUS SCHEDULER                    │
    │  APScheduler → Triggers Planner/Notification      │
    │  - Daily briefing: 9:00 AM                       │
    │  - Overdue follow-up: 6:00 PM                    │
    │  - Weekly summary: Monday 8:00 AM                 │
    └──────────────────────────────────────────────────┘
```

---

## 2. Layer-by-Layer Description

### 2.1 Communication Layer
- **Google Chat Bot**: Registered as a Google Chat app with webhook URL. Receives all user messages as HTTP POST events. Sends responses via Google Chat REST API.
- **Next.js Dashboard**: SPA that consumes the REST Task API. Used by managers for visual oversight.

### 2.2 API Gateway (FastAPI)
- Single entry point for all requests
- Handles: JWT auth, rate limiting (via Redis), CORS, request validation (Pydantic)
- Two routing branches:
  1. **Webhook Handler** — processes Google Chat events → passes to agents
  2. **REST API** — standard CRUD for dashboard

### 2.3 Multi-Agent Orchestration (LangGraph)
See `AGENTS.md` for full contracts.

| Agent | Responsibility |
|-------|---------------|
| Supervisor | Intent classification, agent routing, state management |
| Task Management Agent | All task CRUD operations via tools |
| Planner Agent | Daily planning, prioritization, workload analysis |
| Recommendation Agent | Overdue detection, duplicate detection, insights |
| Review & Validation Agent | Validates destructive actions, business rules |
| Memory Agent | Persistent conversation context, user preferences |

### 2.4 Data & State Layer
- **PostgreSQL**: Primary store for users, tasks, audit logs
- **Redis**: Session state, rate limiting, LangGraph checkpointer (conversation memory), scheduler locks

### 2.5 External AI Layer
- **LiteLLM**: Abstraction over LLM providers — primary Google Gemini 1.5 Pro, fallback to GPT-4o
- Allows model swap without code changes

### 2.6 Autonomous Scheduler
- APScheduler with Redis job store
- Fires agent workflows on schedule
- Sends proactive Google Chat DMs via Chat REST API

### 2.7 Observability Layer
- **LangSmith**: Full LLM call tracing, agent reasoning, token usage
- **Prometheus**: opt-in `/metrics` endpoint (`METRICS_ENABLED`): `orbit_http_requests_total` and `orbit_http_request_duration_seconds` by route template, `orbit_agent_runs_total` and `orbit_agent_run_duration_seconds`, `orbit_tool_calls_total`, `orbit_notifications_total`. Point any Prometheus-compatible stack (Grafana, etc.) at it
- **Python logging**: Structured JSON logs

---

## 3. Data Flow

### 3.1 User Request Flow (Google Chat → Response)
```
User types in Google Chat
  → Google Chat sends POST to /api/chat/webhook
  → FastAPI authenticates the request (Google-signed Bearer token from the Chat service
    account, or HMAC signature; see API.md). A configured HMAC secret makes the signature mandatory
  → Extracts sender, message text, space ID
  → Idempotency check: MESSAGE/CARD_CLICKED events are deduped against
    chat_event_ledger (keyed on message resource name / action+params).
    A redelivered event short-circuits here and is never re-executed.
  → Loads conversation history from Redis (Memory Agent)
  → Supervisor Agent classifies intent
  → Routes to specialist agent
  → Agent calls tools (DB reads/writes via Deterministic Tool Gateway)
  → LLM generates natural language response
  → Review Agent validates response
  → FastAPI sends response to Google Chat via REST API
  → Memory Agent persists updated conversation state
  → Ledger entry finalized as COMPLETED (or FAILED, which allows a future retry)
```

**Idempotency ledger** (`chat_event_ledger`, see `backend/crud/chat_events.py`):
Google Chat may redeliver an event (timeouts, platform retries). The webhook
handler computes a stable `event_key` per event — the Chat message resource
name for `MESSAGE` events, or a hash of `(space, user, eventTime, action,
parameters)` for `CARD_CLICKED` — and atomically claims it via a unique DB
constraint before invoking the agent graph. A duplicate claim returns the
cached response (or a safe generic acknowledgement) without re-running any
tool. A claim that fails before completion is marked `FAILED` so a genuine
retry can still succeed; only `COMPLETED` claims are treated as already
processed. `ADDED_TO_SPACE`/`APP_HOME` events are not deduped since resending
the welcome card has no side effects.

### 3.2 Autonomous Flow (Scheduler → Notification)
```
APScheduler fires at 9:00 (APP_TIMEZONE)
  → Redis lock orbit:lock:scheduler:<job> so only one worker runs it
  → Loads active users, skips anyone opted out (user_preferences)
  → For each user: builds the ranked plan from their tasks
  → services.notifications.deliver_with_retry:
      no Google Chat account  → status "skipped"
      DM space known or found → post, bounded retry → "sent" only on API success, else "failed"
  → Logs the true outcome in notification_logs (visible in Admin, Notifications)
```

### 3.3 Dashboard Flow
```
Next.js page loads
  → Fetches JWT from auth endpoint
  → GET /api/tasks?filters=...
  → FastAPI queries PostgreSQL
  → Returns paginated task list
  → Dashboard renders Kanban/table view
```

### 3.4 Dashboard/Chat → Google Chat Notification Flow
```
Task mutated via POST/PATCH /api/tasks (dashboard) OR via a chat command
  → crud/tasks.py: create_task / update_task / complete_task
  → DB transaction commits (the task mutation is never rolled back for a
    notification failure — this runs strictly after commit)
  → services/notifications.notify_task_event() dispatches when the
    recipient differs from the acting user:
      - create_task with assignee != creator        → "task_assigned"
      - update_task with assignee_id changed         → "task_assigned" (new assignee)
      - update_task with other fields changed        → "task_updated" (current assignee)
      - complete_task by someone other than creator  → "task_completed" (creator)
  → Delivery via services/google_chat.send_dm (or send_text_message as a
    space fallback), with one bounded retry on transient failure
  → Outcome always recorded in notification_logs as sent | failed | skipped
    (skipped = recipient has no linked Google Chat handle) — never marked
    "sent" without an API success response
```
This is the same `NotificationLog` model and delivery path the scheduler
jobs already use for daily briefings and overdue alerts (`scheduler/jobs/`),
so both proactive and event-driven notifications share one audit trail.

---

## 4. Sequence Diagrams

### 4.1 Task Creation
```
User          GChat         FastAPI        Supervisor     TaskAgent      DB
  |  "Create task"  |            |               |              |         |
  |─────────────────►            |               |              |         |
  |             POST /webhook    |               |              |         |
  |             ─────────────────►               |              |         |
  |             |            route_to_agent      |              |         |
  |             |            ────────────────────►              |         |
  |             |            |               create_task_tool  |         |
  |             |            |               ─────────────────►          |
  |             |            |               |              INSERT task   |
  |             |            |               |              ────────────► |
  |             |            |               |              ◄────────────|
  |             |            |               ◄─────────────              |
  |             |            ◄───────────────                            |
  | "Task created: #42"       |               |              |         |
  |◄─────────────────         |               |              |         |
```

---

## 5. Deployment Architecture

```
┌────────────────────────────────────────────┐
│              Docker Compose                 │
│                                             │
│  ┌──────────────┐  ┌──────────────────┐   │
│  │   FastAPI    │  │    Next.js       │   │
│  │   (uvicorn)  │  │    (port 3000)   │   │
│  │   port 8000  │  └──────────────────┘   │
│  └──────┬───────┘                          │
│         │                                   │
│  ┌──────▼───────┐  ┌──────────────────┐   │
│  │  PostgreSQL  │  │     Redis        │   │
│  │  port 5432   │  │     port 6379    │   │
│  └──────────────┘  └──────────────────┘   │
└────────────────────────────────────────────┘
```

---

## 6. Security Architecture

| Concern | Solution |
|---------|---------|
| Google Chat webhook | Google-signed Bearer token verified for the configured audience and the Chat service account identity (both documented audience modes), or HMAC. Production refuses to boot with verification off |
| API auth | JWT Bearer tokens (HS256), 24 hour default; user row re-checked on every request so deactivation is immediate |
| RBAC | `auth/rbac.py` rules used by REST routes **and** by every agent tool (the caller's id is passed to tools, which scope searches, hide foreign tasks, and refuse team data to employees) |
| Brute force | Failed-login limiter per IP + email (Redis, in-memory fallback); successes clear the counter |
| SQL injection | SQLAlchemy ORM parameterised queries; LIKE wildcards escaped; sort columns whitelisted |
| Account takeover | Google sign-in requires password proof before linking to an existing email; public registration off by default |
| Output safety | Dashboard renders agent text as React nodes (never HTML); unhandled errors return a reference id, not exception text |
| Secrets | Environment variables only; production validates strength; seed password required in production |
| Privacy | Webhook payloads not logged by default; directory API hides Google ids and chat spaces |
