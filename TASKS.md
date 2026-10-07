# TASKS.md — Implementation Phases
# ORBIT: Multi-Agent AI Task Management System

**Deadline:** Monday, June 15, 12:00 PM IST  
**Total Estimated Time:** ~42 hours  
**Status Legend:** ⬜ Not Started | 🔄 In Progress | ✅ Done | ❌ Blocked | ⏭️ Skipped

---

## 🗺️ Phase Overview

```
Phase 0  ▶  Phase 1  ▶  Phase 2  ▶  Phase 3  ▶  Phase 4  ▶  Phase 5  ▶  Phase 6  ▶  Phase 7  ▶  Phase 8
 Setup      DB &        REST        Agent       Google      Scheduler   Frontend    Docker &    Polish &
  2h        Auth         API        Tools       Chat Bot    & Notifs    Dashboard   README      Testing
             4h          4h          3h          8h          3h          6h          2h          3h
```

**Cut priority (if short on time):**
> Phase 8 → Phase 7 (keep only table view) → Phase 5 HITL → Phase 6 weekly summary

---

---

## ✅ Phase 0: Project Setup
**Goal:** Runnable skeleton with all dependencies installed.  
**Time:** ~2 hours  
**Deliverable:** `docker-compose up` starts PostgreSQL + Redis. FastAPI says "Hello".

---

### 0.1 — Folder Structure
```
ORBIT/
├── backend/
│   ├── agents/
│   ├── api/
│   ├── crud/
│   ├── db/
│   ├── schemas/
│   ├── services/
│   ├── scheduler/
│   ├── tools/
│   └── main.py
├── frontend/
├── tests/
├── docker-compose.yml
├── .env.example
└── .gitignore
```

| # | Task | Status |
|---|------|--------|
| 0.1 | Create all folders above with `__init__.py` in each backend subfolder | ✅ Done |
| 0.2 | Create `backend/requirements.txt` with all dependencies | ✅ Done |
| 0.3 | Create `.env.example` with every variable needed | ✅ Done |
| 0.4 | Create `docker-compose.yml` (postgres + redis + backend + frontend) | ✅ Done |
| 0.5 | Create `backend/main.py` — bare FastAPI app that returns `{"status": "ok"}` | ✅ Done |
| 0.6 | Init git repo + `.gitignore` (exclude .env, __pycache__, .next) | ✅ Done |

**`requirements.txt` includes:**
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
redis[asyncio]==5.2.0
pydantic[email]==2.10.0
pydantic-settings==2.6.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.28.0
langgraph==0.2.60
langchain-google-genai==2.0.7
langchain-core==0.3.25
litellm==1.56.0
langchain-community==0.3.9
apscheduler==3.10.4
python-dotenv==1.0.1
structlog==24.4.0
```

**✅ Definition of Done:**
- `docker-compose up -d` starts without errors
- `curl http://localhost:8000/` returns `{"status": "ok"}`
- PostgreSQL and Redis containers are healthy

---

---

## ✅ Phase 1: Database & Auth Foundation
**Goal:** Database schema running, models defined, JWT auth working.  
**Time:** ~4 hours  
**Deliverable:** Can create a user, get a JWT, and verify it. Tables exist in Postgres.

---

### 1.1 — Config & App Setup

| # | Task | Status |
|---|------|--------|
| 1.1 | Create `backend/config.py` — pydantic-settings class reading `.env` | ✅ Done |
| 1.2 | Create `backend/main.py` — FastAPI with CORS, lifespan, routers included | ✅ Done |
| 1.3 | Create `backend/dependencies.py` — `get_db()`, `get_current_user()`, `require_role()` | ✅ Done |
| 1.4 | Create global exception handler (`backend/exceptions.py`) | ✅ Done |
| 1.5 | Create response helper `api_response(data, meta, error)` | ✅ Done |

**`config.py` fields:**
```python
DATABASE_URL: str
REDIS_URL: str
JWT_SECRET_KEY: str
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 24
GOOGLE_GEMINI_API_KEY: str
GOOGLE_CHAT_WEBHOOK_SECRET: str
GOOGLE_SERVICE_ACCOUNT_FILE: str
LANGCHAIN_TRACING_V2: bool = False
LANGCHAIN_API_KEY: str = ""
```

---

### 1.2 — Database Models

| # | Task | Status |
|---|------|--------|
| 1.6 | Create `backend/db/session.py` — async engine + session factory | ✅ Done |
| 1.7 | Create `backend/db/models.py` — `User`, `Task`, `TaskAuditLog`, `UserPreference`, `NotificationLog` | ✅ Done |
| 1.8 | Init Alembic: `alembic init alembic` + configure `env.py` | ✅ Done |
| 1.9 | Generate migration: `alembic revision --autogenerate -m "initial schema"` | ✅ Done |
| 1.10 | Apply migration: `alembic upgrade head` | ✅ Done |
| 1.11 | Create `backend/db/seed.py` — insert 3 test users + 5 sample tasks | ✅ Done |

---

### 1.3 — Auth Endpoints

| # | Task | Status |
|---|------|--------|
| 1.12 | Create `backend/auth/jwt.py` — `create_token()`, `decode_token()` | ✅ Done |
| 1.13 | Create `backend/api/auth.py` — `POST /api/auth/token`, `GET /api/auth/me` | ✅ Done |
| 1.14 | Create `backend/schemas/auth.py` — `TokenRequest`, `TokenResponse` | ✅ Done |
| 1.15 | Register auth router in `main.py` | ✅ Done |

**✅ Definition of Done:**
- `GET /api/health` → `{"database": "connected", "redis": "connected"}`
- `POST /api/auth/token` with valid email/password returns JWT
- `GET /api/auth/me` with Bearer token returns user object
- `alembic upgrade head` applies cleanly — all 5 tables exist in PostgreSQL

---

---

## ✅ Phase 2: Task & User REST API
**Goal:** Full CRUD API for tasks and users. Dashboard can consume this directly.  
**Time:** ~4 hours  
**Deliverable:** All task endpoints working, testable via `/docs` Swagger UI.

---

### 2.1 — Schemas (Pydantic)

| # | Task | Status |
|---|------|--------|
| 2.1 | Create `backend/schemas/user.py` — `UserCreate`, `UserRead`, `UserUpdate` | ✅ Done |
| 2.2 | Create `backend/schemas/task.py` — `TaskCreate`, `TaskRead`, `TaskUpdate`, `TaskListResponse` | ✅ Done |
| 2.3 | Create `backend/schemas/common.py` — `PaginationMeta`, `APIResponse[T]` | ✅ Done |

---

### 2.2 — CRUD Layer

| # | Task | Status |
|---|------|--------|
| 2.4 | Create `backend/crud/users.py` — `get_user_by_id`, `get_user_by_google_id`, `get_user_by_name`, `get_all_users`, `create_user`, `update_user` | ✅ Done |
| 2.5 | Create `backend/crud/tasks.py` — `create_task`, `get_task`, `update_task`, `soft_delete_task`, `complete_task`, `search_tasks`, `get_user_tasks`, `get_overdue_tasks`, `get_tasks_due_today`, `get_task_stats` | ✅ Done |
| 2.6 | Create `backend/crud/audit.py` — `log_task_action(task_id, user_id, action, changes)` | ✅ Done |

---

### 2.3 — API Routers

| # | Task | Status |
|---|------|--------|
| 2.7 | Create `backend/api/tasks.py` — all 8 task endpoints | ✅ Done |
| 2.8 | Create `backend/api/users.py` — list, get, update me, get user tasks | ✅ Done |
| 2.9 | Create `backend/api/analytics.py` — `/stats`, `/team-workload` | ✅ Done |
| 2.10 | Create `backend/api/health.py` — `GET /api/health` | ✅ Done |
| 2.11 | Register all routers in `main.py` | ✅ Done |

**Task endpoints to build:**
```
GET    /api/tasks              list with filters + pagination
POST   /api/tasks              create task
GET    /api/tasks/{id}         get task + audit history
PATCH  /api/tasks/{id}         partial update
DELETE /api/tasks/{id}         soft delete (MANAGER only)
POST   /api/tasks/{id}/complete  mark complete
GET    /api/tasks/{id}/history   audit trail
```

**✅ Definition of Done:**
- All endpoints visible at `http://localhost:8000/docs`
- Can create, list, update, complete a task via Swagger UI
- Full-text search works: `GET /api/tasks?q=frontend` returns matching tasks
- Pagination works: `GET /api/tasks?page=2&page_size=5`
- Audit log entry created for every mutation

---

---

## ✅ Phase 3: Agent Tools
**Goal:** Pure Python functions (LangChain tools) that agents will call.  
**Time:** ~3 hours  
**Deliverable:** Each tool is independently unit-testable against a mocked DB.

---

### 3.1 — Task Tools

| # | Task | Status |
|---|------|--------|
| 3.1 | Create `backend/tools/task_tools.py` | ✅ Done |
| 3.2 | Implement `create_task` tool (wraps `crud.tasks.create_task`) | ✅ Done |
| 3.3 | Implement `get_task_by_id` tool | ✅ Done |
| 3.4 | Implement `update_task` tool | ✅ Done |
| 3.5 | Implement `complete_task` tool | ✅ Done |
| 3.6 | Implement `delete_task` tool | ✅ Done |
| 3.7 | Implement `search_tasks` tool | ✅ Done |
| 3.8 | Implement `get_user_tasks` tool | ✅ Done |
| 3.9 | Implement `get_overdue_tasks` tool | ✅ Done |
| 3.10 | Implement `get_tasks_due_today` tool | ✅ Done |

---

### 3.2 — User & Analytics Tools

| # | Task | Status |
|---|------|--------|
| 3.11 | Create `backend/tools/user_tools.py` — `get_user_by_name`, `get_all_users`, `get_team_workload` | ✅ Done |
| 3.12 | Create `backend/tools/analytics_tools.py` — `get_task_stats` | ✅ Done |

---

### 3.3 — Formatting Tools

| # | Task | Status |
|---|------|--------|
| 3.13 | Create `backend/tools/format_tools.py` — `format_task_card()` returns Google Chat card JSON | ✅ Done |
| 3.14 | Create `backend/tools/format_tools.py` — `format_task_list_text()` returns markdown text | ✅ Done |

**Tool structure pattern:**
```python
# Every tool follows this pattern
@tool
async def create_task(
    title: str,
    priority: str = "MEDIUM",
    assignee_name: str | None = None,
    due_date: str | None = None,
    created_by_id: str = ""
) -> dict:
    """Create a new task. Returns the created task or an error."""
    try:
        async with get_db_session() as db:
            # resolve assignee by name if needed
            # call crud function
            # log audit
            return {"success": True, "data": task.model_dump()}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

**✅ Definition of Done:**
- Each tool can be invoked directly in a Python script without agents
- Tools return `{"success": True, "data": ...}` on success
- Tools return `{"success": False, "error": "..."}` on failure (never raise)
- `get_user_by_name("John")` correctly resolves to `User` from seed data

---

---

## ✅ Phase 4: Multi-Agent System ⭐ MOST CRITICAL
**Goal:** Full LangGraph agent pipeline running locally — no Google Chat yet, just Python.  
**Time:** ~8 hours  
**Deliverable:** `await graph.ainvoke(state)` processes natural language and returns correct response.

---

### 4.1 — Shared State & Prompts

| # | Task | Status |
|---|------|--------|
| 4.1 | Create `backend/agents/state.py` — `AgentState` TypedDict (see AGENTS.md §2) | ✅ Done |
| 4.2 | Create `backend/agents/intents.py` — `Intent` enum + `IntentClassification` Pydantic model | ✅ Done |
| 4.3 | Create `backend/agents/prompts.py` — all system prompts as constants | ✅ Done |
| 4.4 | Create `backend/services/llm.py` — LiteLLM client setup, model config | ✅ Done |

**`prompts.py` contains:**
```python
SUPERVISOR_PROMPT = "..."    # Intent classification
TASK_AGENT_PROMPT = "..."    # Task CRUD reasoning
PLANNER_PROMPT = "..."       # Daily planning
RECOMMENDATION_PROMPT = "..." # Insights & overdue
REVIEW_PROMPT = "..."         # Validation & HITL
```

---

### 4.2 — Individual Agents

| # | Task | Status |
|---|------|--------|
| 4.5 | Create `backend/agents/memory_agent.py` — load/save Redis checkpoints | ✅ Done |
| 4.6 | Create `backend/agents/supervisor.py` — LLM classification → Intent + TaskContext | ✅ Done |
| 4.7 | Create `backend/agents/task_agent.py` — LLM with TASK_AGENT_TOOLS | ✅ Done |
| 4.8 | Create `backend/agents/planner_agent.py` — LLM with PLANNER_TOOLS | ✅ Done |
| 4.9 | Create `backend/agents/recommendation_agent.py` — LLM with RECOMMENDATION_TOOLS | ✅ Done |
| 4.10 | Create `backend/agents/review_agent.py` — HITL validation | ✅ Done |

---

### 4.3 — LangGraph Assembly

| # | Task | Status |
|---|------|--------|
| 4.11 | Create `backend/agents/graph.py` — `StateGraph` with all nodes + edges | ✅ Done |
| 4.12 | Implement `route_to_agent()` conditional edge function | ✅ Done |
| 4.13 | Implement `check_confirmation()` conditional edge (Review Agent) | ✅ Done |
| 4.14 | Compile graph with `AsyncRedisSaver` checkpointer | ✅ Done |
| 4.15 | Create `backend/agents/orchestrator.py` — `process_message(user_id, space_id, message)` → `str` | ✅ Done |

---

### 4.4 — Local Testing (no Google Chat)

| # | Task | Status |
|---|------|--------|
| 4.16 | Create `backend/scripts/test_agent.py` — CLI script to test agents | ✅ Done |
| 4.17 | Test all 8 intents from `EVALUATION.md §3.1` manually | ✅ Done |
| 4.18 | Verify multi-turn memory works (reference "it" in turn 2) | ✅ Done |

**Test script:**
```python
# python -m backend.scripts.test_agent
import asyncio
from backend.agents.orchestrator import process_message

async def main():
    user_id = "seed-user-1"
    space_id = "test-space"
    
    tests = [
        "Create a high priority task for John to deploy the frontend by Friday",
        "Show my pending tasks",
        "What should I focus on today?",
        "Mark the CRM deployment task as completed",
    ]
    for msg in tests:
        print(f"\nUser: {msg}")
        response = await process_message(user_id, space_id, msg)
        print(f"ORBIT: {response}")

asyncio.run(main())
```

**✅ Definition of Done:**
- All 8 test intents return correct, non-empty responses
- `CREATE_TASK` → task appears in DB
- `GET_MY_TASKS` → lists tasks from DB
- `PLAN_DAY` → returns ordered priority list with reasoning
- Multi-turn test: create task → "make it high priority" → task updated
- LangSmith shows full agent trace (if enabled)

---

---

## ✅ Phase 5: Google Chat Integration ⭐ MOST CRITICAL
**Goal:** Real Google Chat messages trigger the agent system and send back responses.  
**Time:** ~8 hours  
**Deliverable:** Type a message in Google Chat → ORBIT bot responds with task info.

---

### 5.1 — Google Chat Service

| # | Task | Status |
|---|------|--------|
| 5.1 | Create `backend/services/google_chat.py` | ⬜ |
| 5.2 | Implement `send_text_message(space_id, text)` → POST to Chat API | ⬜ |
| 5.3 | Implement `send_card_message(space_id, card_json)` → POST to Chat API | ⬜ |
| 5.4 | Implement `send_dm(google_user_id, text)` — for proactive notifications | ⬜ |
| 5.5 | Implement `verify_webhook_signature(body, signature)` | ⬜ |

---

### 5.2 — Webhook Handler

| # | Task | Status |
|---|------|--------|
| 5.6 | Create `backend/api/webhook.py` — `POST /api/chat/webhook` | ⬜ |
| 5.7 | Handle `MESSAGE` event → extract sender + text → `process_message()` → send response | ⬜ |
| 5.8 | Handle `CARD_CLICKED` event → HITL confirmation flow | ⬜ |
| 5.9 | Handle `ADDED_TO_SPACE` event → welcome message | ⬜ |
| 5.10 | Auto-register/upsert Google user in DB on first message | ⬜ |
| 5.11 | Return `200 OK` immediately, process in background task | ⬜ |
| 5.12 | Register webhook router in `main.py` | ⬜ |

**Webhook handler pattern:**
```python
@router.post("/api/chat/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Goog-Signature", "")
    
    # 1. Verify signature (return 403 if invalid)
    verify_webhook_signature(body, signature)
    
    # 2. Parse event
    event = GoogleChatEvent.model_validate_json(body)
    
    # 3. Process in background (avoid 30s timeout)
    background_tasks.add_task(handle_event, event)
    
    # 4. Return 200 immediately
    return {"status": "accepted"}
```

---

### 5.3 — Google Chat Bot Registration

| # | Task | Status |
|---|------|--------|
| 5.13 | Create Google Cloud project + enable Chat API | ⬜ |
| 5.14 | Create service account + download JSON credentials | ⬜ |
| 5.15 | Configure bot in Google Chat API console (webhook URL) | ⬜ |
| 5.16 | Expose local server via `ngrok` for webhook testing | ⬜ |
| 5.17 | Test: add bot to DM space → send "hello" → get response | ⬜ |

**ngrok command:**
```bash
ngrok http 8000
# Use https://xxx.ngrok-free.app/api/chat/webhook as webhook URL
```

**✅ Definition of Done:**
- ORBIT bot appears in Google Chat
- "Create a task for John to deploy frontend by Friday" → bot confirms task created
- "Show my tasks" → bot returns task list
- Bot DM works (will be needed for scheduler)

---

---

## ✅ Phase 6: Autonomous Scheduler
**Goal:** Proactive daily briefings and overdue alerts sent automatically.  
**Time:** ~3 hours  
**Deliverable:** Set system time to 9 AM → users receive a morning briefing in Google Chat DM.

---

### 6.1 — Scheduler Setup

| # | Task | Status |
|---|------|--------|
| 6.1 | Create `backend/scheduler/scheduler.py` — APScheduler with Redis job store | ⬜ |
| 6.2 | Register scheduler start/stop in FastAPI lifespan (`main.py`) | ⬜ |

```python
# backend/scheduler/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": RedisJobStore(redis_url=settings.REDIS_URL)},
    timezone="Asia/Kolkata"
)
```

---

### 6.2 — Scheduler Jobs

| # | Task | Status |
|---|------|--------|
| 6.3 | Create `backend/scheduler/jobs/daily_briefing.py` | ⬜ |
| 6.4 | Job logic: load active users → for each: PlannerAgent → send DM → log | ⬜ |
| 6.5 | Register job: `cron(hour=9, minute=0)` | ⬜ |
| 6.6 | Create `backend/scheduler/jobs/overdue_alert.py` | ⬜ |
| 6.7 | Job logic: find overdue tasks → group by assignee → RecommendationAgent → send DM | ⬜ |
| 6.8 | Register job: `cron(hour=18, minute=0)` | ⬜ |
| 6.9 | Create `backend/scheduler/jobs/weekly_summary.py` (OPTIONAL) | ⬜ |
| 6.10 | Add `POST /api/admin/trigger-briefing` debug endpoint (manual trigger) | ⬜ |

**✅ Definition of Done:**
- Trigger `POST /api/admin/trigger-briefing` → all users receive DM in Google Chat
- Duplicate-send check works (only one briefing per day per user)
- Scheduler logs show job execution times

---

---

## ✅ Phase 7: Frontend Dashboard
**Goal:** Next.js dashboard where users can view, search, filter, and manage tasks.  
**Time:** ~6 hours  
**Deliverable:** Dashboard shows live tasks from API with search + filter + task detail.

---

### 7.1 — Project Init & API Client

| # | Task | Status |
|---|------|--------|
| 7.1 | `npx create-next-app@14 frontend --typescript --tailwind --app --no-src-dir` | ⬜ |
| 7.2 | Install deps: `@tanstack/react-query`, `axios`, `recharts`, `lucide-react` | ⬜ |
| 7.3 | Create `frontend/lib/api-client.ts` — typed wrapper for all ORBIT API calls | ⬜ |
| 7.4 | Create `frontend/lib/auth.ts` — login, store JWT, auth context | ⬜ |
| 7.5 | Create `frontend/types/index.ts` — `Task`, `User`, `APIResponse` types | ⬜ |
| 7.6 | Setup TanStack Query provider in `layout.tsx` | ⬜ |

---

### 7.2 — Layout & Auth

| # | Task | Status |
|---|------|--------|
| 7.7 | Create `app/login/page.tsx` — login form | ⬜ |
| 7.8 | Create `app/layout.tsx` — sidebar nav (Dashboard, Tasks, Analytics, Settings) | ⬜ |
| 7.9 | Create `components/Sidebar.tsx` with nav links | ⬜ |
| 7.10 | Create `middleware.ts` — redirect to login if no JWT | ⬜ |

---

### 7.3 — Task List Page (Core)

| # | Task | Status |
|---|------|--------|
| 7.11 | Create `app/tasks/page.tsx` — task table with TanStack Query | ⬜ |
| 7.12 | Create `components/TaskTable.tsx` — sortable columns | ⬜ |
| 7.13 | Create `components/FilterBar.tsx` — status, priority, assignee, date filters | ⬜ |
| 7.14 | Create `components/SearchBar.tsx` — debounced search (300ms) | ⬜ |
| 7.15 | Create `components/StatusBadge.tsx` — colored status pills | ⬜ |
| 7.16 | Create `components/PriorityBadge.tsx` — colored priority pills | ⬜ |
| 7.17 | Create `components/Pagination.tsx` | ⬜ |

---

### 7.4 — Task Detail

| # | Task | Status |
|---|------|--------|
| 7.18 | Create `app/tasks/[id]/page.tsx` — full task detail view | ⬜ |
| 7.19 | Show: title, description, assignee, priority, status, due date, audit history | ⬜ |
| 7.20 | Add "Mark Complete" + "Edit" buttons | ⬜ |

---

### 7.5 — Dashboard / Kanban

| # | Task | Status |
|---|------|--------|
| 7.21 | Create `app/page.tsx` — Kanban board (4 columns: TODO, IN_PROGRESS, REVIEW, DONE) | ⬜ |
| 7.22 | Create `components/KanbanColumn.tsx` | ⬜ |
| 7.23 | Create `components/TaskCard.tsx` — compact card for kanban | ⬜ |
| 7.24 | Show stats summary at top (total, overdue, completed today) | ⬜ |

---

### 7.6 — Analytics Page (OPTIONAL)

| # | Task | Status |
|---|------|--------|
| 7.25 | Create `app/analytics/page.tsx` | ⬜ |
| 7.26 | Add completion rate donut chart (Recharts) | ⬜ |
| 7.27 | Add tasks-per-day bar chart | ⬜ |
| 7.28 | Add team workload horizontal bar chart | ⬜ |

**✅ Definition of Done:**
- `http://localhost:3000` shows Kanban or task table with real data from API
- Search works — type "frontend" → filtered results appear
- Filter by status/priority works
- Task detail page shows audit history
- Login page works with seeded user credentials

---

---

## ✅ Phase 8: Docker, README & Polish
**Goal:** Everything runs with one command. Documentation is submission-ready.  
**Time:** ~2 hours  

| # | Task | Status |
|---|------|--------|
| 8.1 | Write `backend/Dockerfile` (multi-stage, python:3.11-slim) | ⬜ |
| 8.2 | Write `frontend/Dockerfile` (multi-stage, node:20-alpine) | ⬜ |
| 8.3 | Finalize `docker-compose.yml` with health checks on all services | ⬜ |
| 8.4 | Write final `README.md` with setup + example interactions | ⬜ |
| 8.5 | Write `ARCHITECTURE_EVALUATION.md` (required: thoughts on the diagram tool) | ⬜ |
| 8.6 | Record 3–5 min demo video covering all use cases | ⬜ |

**✅ Definition of Done:**
- `git clone → cp .env.example .env → docker-compose up -d` works from scratch
- All services healthy after 60s
- README has architecture diagram embedded
- Demo video shows: bot interaction + dashboard + scheduler

---

---

## ✅ Phase 9: Testing (if time allows)
**Goal:** Key paths are regression-proof.  
**Time:** ~3 hours  

| # | Task | Status |
|---|------|--------|
| 9.1 | Unit test all 10 task tools (`tests/unit/test_task_tools.py`) | ⬜ |
| 9.2 | Integration test all task API endpoints (`tests/integration/test_tasks_api.py`) | ⬜ |
| 9.3 | Intent classification eval (`tests/eval/test_intent_accuracy.py`) — runs 8 test cases | ⬜ |
| 9.4 | End-to-end manual test log (`tests/manual/e2e_checklist.md`) | ⬜ |

---

---

## ⚡ Time Budget Summary

| Phase | Name | Time | Priority |
|-------|------|------|----------|
| 0 | Setup | 2h | MUST |
| 1 | DB & Auth | 4h | MUST |
| 2 | REST API | 4h | MUST |
| 3 | Agent Tools | 3h | MUST |
| **4** | **Multi-Agent System** | **8h** | **⭐ CRITICAL** |
| **5** | **Google Chat** | **8h** | **⭐ CRITICAL** |
| 6 | Scheduler | 3h | MUST |
| 7 | Frontend | 6h | SHOULD |
| 8 | Docker + README | 2h | MUST |
| 9 | Testing | 3h | OPTIONAL |
| | **TOTAL** | **43h** | |
