# ARCHITECTURE.md — System Architecture
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Last Updated:** 2026-10-07

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
- **Prometheus + Grafana**: API latency, error rate, task throughput
- **Python logging**: Structured JSON logs

---

## 3. Data Flow

### 3.1 User Request Flow (Google Chat → Response)
```
User types in Google Chat
  → Google Chat sends POST to /api/chat/webhook
  → FastAPI verifies webhook signature
  → Extracts sender, message text, space ID
  → Loads conversation history from Redis (Memory Agent)
  → Supervisor Agent classifies intent
  → Routes to specialist agent
  → Agent calls tools (DB reads/writes via Deterministic Tool Gateway)
  → LLM generates natural language response
  → Review Agent validates response
  → FastAPI sends response to Google Chat via REST API
  → Memory Agent persists updated conversation state
```

### 3.2 Autonomous Flow (Scheduler → Notification)
```
APScheduler fires at 9:00 AM
  → Loads all active users from DB
  → For each user: Planner Agent generates daily briefing
  → Sends DM to user via Google Chat REST API
  → Logs delivery in DB
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
| Google Chat webhook | Verify `X-Goog-Signature` header |
| API auth | JWT Bearer tokens (HS256) |
| RBAC | Role check middleware (employee/manager/admin) |
| SQL injection | SQLAlchemy ORM (parameterized queries) |
| Rate limiting | Redis sliding window per user |
| Secrets | Environment variables (.env), never committed |
