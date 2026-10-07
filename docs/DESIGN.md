# DESIGN.md — Technical Design & Technology Decisions
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Last Updated:** 2026-10-07

---

## 1. Technology Stack

| Layer | Technology | Version | Reason |
|-------|-----------|---------|--------|
| Backend Framework | FastAPI | 0.115+ | Async-native, Pydantic validation, OpenAPI auto-docs, high performance |
| Language | Python | 3.11+ | Best LLM/agent ecosystem, async support, type hints |
| Agent Framework | LangGraph | 0.2+ | Stateful graph-based agents, native cycles, checkpointing, production-ready |
| LLM Primary | Google Gemini 1.5 Pro | via LiteLLM | Free tier, strong reasoning, native Google ecosystem |
| LLM Abstraction | LiteLLM | 1.x | Provider-agnostic, automatic fallback, cost tracking |
| Database | PostgreSQL | 16 | ACID compliance, JSON columns, full-text search, pgvector ready |
| ORM | SQLAlchemy | 2.0+ | Async ORM, modern API, migration support |
| Migrations | Alembic | latest | Schema versioning, rollback support |
| Cache / State | Redis | 7+ | Fast in-memory store for sessions, rate limiting, LangGraph checkpointer |
| Scheduler | APScheduler | 3.x | Lightweight, Python-native, Redis job store |
| Communication | Google Chat API | v1 | Webhook + REST, card messages, DM support |
| Frontend | Next.js | 14 (App Router) | SSR, TypeScript, API routes, Vercel-ready |
| Frontend Styling | Tailwind CSS | 3.x | Rapid UI, consistent design system |
| Frontend State | TanStack Query | 5.x | Server state management, caching, auto-refresh |
| Containerization | Docker + Compose | 27+ | Dev/prod parity, easy deployment |
| Observability | LangSmith | cloud | LLM tracing, agent step visualization |
| Metrics | Prometheus + Grafana | latest | API metrics, custom business metrics |
| Logging | Python logging + structlog | - | JSON-structured logs |
| Testing | pytest + pytest-asyncio | - | Async test support |
| API Testing | httpx | - | Async HTTP client for FastAPI tests |

---

## 2. Key Design Decisions

### 2.1 Why LangGraph over CrewAI / AutoGen?

| Criteria | LangGraph | CrewAI | AutoGen |
|---------|-----------|--------|---------|
| Stateful graphs | ✅ Native | ❌ Limited | ❌ Limited |
| Deterministic routing | ✅ Yes | ❌ LLM-driven | ⚠️ Partial |
| Human-in-the-loop | ✅ Native | ⚠️ Add-on | ⚠️ Add-on |
| Checkpointing | ✅ Built-in | ❌ No | ❌ No |
| Production usage | ✅ LangChain-backed | ⚠️ Growing | ⚠️ Research |
| Debugging | ✅ LangSmith | ⚠️ Limited | ⚠️ Limited |

**Decision**: LangGraph gives us stateful, deterministic agent routing with built-in checkpointing for conversation memory and human-in-the-loop support.

### 2.2 Why PostgreSQL over MongoDB?

- Tasks have relational structure (users, tasks, audit logs, assignments)
- Foreign key constraints enforce data integrity
- Full-text search via `tsvector` for task search
- Can add `pgvector` extension for semantic search later
- ACID compliance critical for task state transitions

### 2.3 Why Redis for Conversation State?

- LangGraph's `AsyncRedisSaver` stores conversation checkpoints keyed by thread_id (space_id + user_id)
- Sub-millisecond reads for active conversations
- TTL-based expiry for idle conversations (24h)
- Also used for: rate limiting, scheduler locks, session cache

### 2.4 Why APScheduler over Celery?

For v1.0, APScheduler with Redis job store is sufficient:
- No separate broker process needed (Redis doubles as broker)
- Python-native, easy to test
- Supports cron expressions, interval jobs
- If scale requires it, can migrate to Celery Beat (same Redis broker)

### 2.5 Why LiteLLM?

- Single interface for Gemini, OpenAI, Anthropic, local models
- Automatic retry and fallback: Gemini → GPT-4o
- Token counting, cost tracking per call
- Zero code changes to swap models

### 2.6 Supervisor Pattern vs. Fully LLM-Driven Routing

**Problem**: Pure LLM-based routing is unpredictable and expensive.  
**Solution**: Hybrid approach:
1. Supervisor Agent classifies intent using a structured prompt → returns enum: `CREATE_TASK | UPDATE_TASK | DELETE_TASK | GET_TASKS | PLAN | RECOMMEND | UNKNOWN`
2. Python code routes to the correct agent based on this enum
3. Specialist agent then uses LLM reasoning with tools

This gives us **deterministic routing** with **LLM understanding**.

---

## 3. Agent Communication Pattern

```
Supervisor
    │
    ├── classified intent: CREATE_TASK
    │       └── TaskManagementAgent.run(state)
    │               └── calls: create_task_tool(params)
    │                       └── DeterministicToolGateway.create_task()
    │                               └── PostgreSQL INSERT
    │
    ├── classified intent: PLAN
    │       └── PlannerAgent.run(state)
    │               └── calls: get_user_tasks_tool(), prioritize_tool()
    │
    └── classified intent: RECOMMEND
            └── RecommendationAgent.run(state)
                    └── calls: get_overdue_tasks_tool(), detect_duplicates_tool()
```

---

## 4. State Schema (LangGraph AgentState)

```python
class AgentState(TypedDict):
    # Input
    user_id: str
    space_id: str
    message: str
    
    # Routing
    intent: str                    # classified intent
    active_agent: str              # which agent is running
    
    # Conversation memory
    messages: list[BaseMessage]    # full conversation history
    
    # Task context
    task_context: dict             # extracted task fields from NL
    confirmed_action: bool         # human-in-the-loop flag
    
    # Output
    response: str                  # final response to send to Chat
    tool_calls_made: list[str]     # audit trail
    error: str | None              # error message if any
```

---

## 5. API Design Pattern

### RESTful Convention
- `GET /api/tasks` — list with filters
- `POST /api/tasks` — create
- `GET /api/tasks/{id}` — get by ID
- `PATCH /api/tasks/{id}` — partial update
- `DELETE /api/tasks/{id}` — soft delete
- `POST /api/tasks/{id}/complete` — mark complete (explicit action endpoint)

### Response Envelope
```json
{
  "success": true,
  "data": { ... },
  "meta": { "page": 1, "total": 42 },
  "error": null
}
```

---

## 6. Google Chat Integration Design

### Bot Registration
- Service account with domain-wide delegation
- Webhook URL: `POST /api/chat/webhook`
- Slash commands: `/tasks`, `/plan`, `/help`

### Message Types Supported
1. **Text response**: Simple markdown string
2. **Card response**: Structured Google Chat card with task details
3. **Confirmation dialog**: Interactive card for destructive actions (HITL)

### Webhook Verification
```python
# Verify X-Goog-Signature header using HMAC-SHA256
import hmac, hashlib
expected = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
assert hmac.compare_digest(expected, received_signature)
```

---

## 7. Frontend Design

### Pages
| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Kanban board with all tasks |
| `/tasks` | Task List | Table view with filters |
| `/tasks/[id]` | Task Detail | Full task info + history |
| `/analytics` | Analytics | Charts, productivity metrics |
| `/settings` | Settings | User preferences |

### Component Architecture
```
app/
  layout.tsx          # Root layout, nav, auth
  page.tsx            # Dashboard/Kanban
  tasks/
    page.tsx          # Task table with filters
    [id]/page.tsx     # Task detail
  analytics/
    page.tsx          # Charts
components/
  TaskCard.tsx        # Kanban card
  TaskTable.tsx       # Table view
  FilterBar.tsx       # Search + filter UI
  TaskDetail.tsx      # Side panel
  StatusBadge.tsx     # Status pill
  PriorityBadge.tsx   # Priority pill
  Charts/             # Recharts wrappers
```

---

## 8. Error Handling Strategy

| Layer | Strategy |
|-------|---------|
| FastAPI | Global exception handler → standard error envelope |
| LLM calls | Retry 3x with exponential backoff via LiteLLM |
| Agent failures | Supervisor catches and returns graceful message |
| DB errors | SQLAlchemy rollback, log error, return 500 |
| Webhook | Return 200 immediately, process async to avoid timeout |
| Scheduler | Failed jobs logged, retried next cycle |
