# RULES.md — Coding & Architecture Constraints
# ORBIT: Multi-Agent AI Task Management System

**IMPORTANT: Every developer and AI agent working on this project MUST read and follow these rules.**

---

## 1. Python / Backend Rules

### 1.1 Code Style
- Use **Python 3.11+** features (union types `X | Y`, `match` statements)
- All functions must have **type hints** — no bare `def func(x):`
- Use **Pydantic v2** for all data validation — no manual dict parsing
- All database operations must use **async SQLAlchemy** (`async with session`)
- Maximum function length: **50 lines** — extract helpers otherwise
- Use **dataclasses** or **TypedDict** for internal data contracts (not dicts)

### 1.2 Error Handling
- **Never use bare `except:`** — always catch specific exceptions
- All FastAPI routes must have **try/except** with proper HTTP responses
- LLM calls must have **retry logic** (max 3 attempts, exponential backoff)
- Database errors must **rollback** the session and log the error
- Return `ToolResult` with `success=False` from tools — never raise inside tool

### 1.3 Async Rules
- All database calls must be **async** — no `session.execute()`, use `await session.execute()`
- All HTTP calls (Google Chat API) must use **httpx.AsyncClient**
- Background tasks must NOT block the event loop
- Scheduler jobs run in **thread pool executor** if they contain sync code

### 1.4 Security Rules
- **NEVER hardcode secrets** — use environment variables via `pydantic-settings`
- **NEVER log** JWT tokens, Google API keys, or user PII
- All webhook requests must **verify signature** before processing
- All SQL queries must go through **SQLAlchemy ORM** — no raw f-string SQL
- JWT tokens expire in **24 hours** max

---

## 2. Agent / LLM Rules

### 2.1 LLM Calls
- All LLM calls go through **LiteLLM** — never call `openai.chat` or `google.generativeai` directly
- Always set **max_tokens** to prevent runaway responses
- Always set **temperature** explicitly (0.1 for classification, 0.7 for generation)
- LLM responses for structured data must use **`.with_structured_output()`** — never parse JSON strings manually
- Log every LLM call with LangSmith via `LANGCHAIN_TRACING_V2=true`

### 2.2 Agent Design
- **Supervisor routes, specialists execute** — supervisor never calls DB directly
- Agent tools must be **idempotent** where possible
- Each agent node must return a **complete AgentState** — no partial returns
- Agents must handle `UNKNOWN` intent gracefully with a helpful prompt
- Maximum LangGraph graph cycles: **10** — add `recursion_limit=10` to config

### 2.3 Prompt Rules
- All system prompts live in **`backend/agents/prompts.py`** — never inline in agent code
- System prompts must be **version-tagged** (add `v{N}` comment header)
- When extracting structured data from NL, always include **fallback defaults**

---

## 3. Database Rules

### 3.1 Migrations
- **All schema changes go through Alembic migrations** — never `ALTER TABLE` manually
- Migration files must be **reviewed before applying to prod**
- Every migration must have an **`upgrade()` and `downgrade()` function**
- Migrations are run at **container startup** (`alembic upgrade head`)

### 3.2 Data Integrity
- **Never hard-delete tasks** — always soft-delete (`deleted_at = NOW()`)
- All task mutations must create an **audit log entry**
- Foreign key constraints must be maintained — use `ON DELETE SET NULL` or `CASCADE` as appropriate
- Timestamps must always be **timezone-aware** (use `TIMESTAMPTZ`)

### 3.3 Queries
- All list endpoints must be **paginated** (default 20, max 100)
- **Never `SELECT *`** — always specify columns in SQLAlchemy
- Add `WHERE deleted_at IS NULL` filter to all task queries by default
- Use **partial indexes** (`WHERE deleted_at IS NULL`) for performance

---

## 4. API Rules

### 4.1 REST Conventions
- Use proper HTTP verbs: `GET` (read), `POST` (create), `PATCH` (partial update), `DELETE` (soft delete)
- All responses follow the **standard envelope**: `{success, data, meta, error}`
- All list endpoints return **pagination metadata** in `meta`
- Use `POST /tasks/{id}/complete` for state transitions — not `PATCH` with `status=DONE`
- Return `201 Created` for new resources, `200 OK` for updates

### 4.2 Validation
- All request bodies validated with **Pydantic models**
- All path parameters validated as **UUID** where applicable
- Date fields must be **ISO 8601** format

---

## 5. Frontend Rules

### 5.1 Next.js
- Use **App Router** (not Pages Router)
- All data fetching via **TanStack Query** — no raw `fetch` in components
- API calls go through a **typed API client** (`lib/api-client.ts`)
- Use **TypeScript strict mode** — `"strict": true` in tsconfig

### 5.2 State Management
- Server state: **TanStack Query**
- UI state: **React useState/useReducer** (no Redux for now)
- Global auth state: **React Context + localStorage**

---

## 6. Testing Rules

- Every tool function must have **unit tests** with mocked DB
- Every API endpoint must have **integration tests** using `httpx.AsyncClient`
- Agent tests must use **recorded LLM responses** (no real API calls in CI)
- Test files named `test_{module}.py` placed in `tests/` mirroring `backend/` structure
- Minimum **60% test coverage** for backend code

---

## 7. Git Rules

- Branch naming: `feature/`, `fix/`, `chore/`, `docs/`
- Commit messages follow **Conventional Commits**: `feat:`, `fix:`, `docs:`, `test:`
- **Never commit** `.env` files or API keys
- PR must pass all tests before merge
- Tag releases with **SemVer**: `v1.0.0`

---

## 8. Docker Rules

- Each service runs in **its own container**
- Use **multi-stage builds** for production images
- **Never use `latest` tag** in production — pin versions
- Health checks defined for all services in `docker-compose.yml`
- Environment variables via `.env` file (`.env.example` committed, `.env` gitignored)
