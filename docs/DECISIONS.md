# DECISIONS.md — Architecture Decision Records (ADRs)
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Last Updated:** 2026-10-07

---

## ADR-001: Use LangGraph for Agent Orchestration

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Need to orchestrate 5+ specialized agents with shared state, conditional routing, and conversation memory.

**Decision**: Use LangGraph (by LangChain) as the agent orchestration framework.

**Alternatives Considered**:
| Option | Pros | Cons |
|--------|------|------|
| LangGraph | Stateful, deterministic routing, Redis checkpointing, HITL support, production-ready | Learning curve |
| CrewAI | Easy to set up, agent roles concept | LLM-driven routing (unpredictable), no native checkpointing |
| AutoGen | Research-proven, multi-agent conversation | Not production-stable, limited tool support |
| Custom orchestrator | Full control | 2–3x more development time |

**Rationale**: LangGraph's `StateGraph` gives us explicit routing logic (not LLM-driven), built-in Redis checkpointing for conversation memory, and native HITL support — all critical requirements.

---

## ADR-002: Supervisor Pattern vs. Fully Decentralized Agents

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: How should agents communicate and route tasks?

**Decision**: Implement a **Supervisor/Router pattern** where the Supervisor classifies intent and routes to specialist agents. Specialist agents do not communicate with each other directly.

**Rationale**:
- Deterministic routing — no LLM decides which agent runs next
- Easier to debug — clear single path through the graph
- Avoids agent "loops" where agents bounce tasks back and forth
- Specialist agents are stateless — easier to test in isolation

**Trade-off**: Less "emergent" behavior — agents can't collaborate dynamically. Acceptable for v1.0.

---

## ADR-003: Google Gemini as Primary LLM via LiteLLM

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Need to choose an LLM provider for agent reasoning.

**Decision**: Use **Google Gemini 1.5 Pro** as primary model, accessed through **LiteLLM** for provider abstraction.

**Rationale**:
- Gemini has a generous free tier for development
- Strong reasoning capabilities for structured output extraction
- Native Google ecosystem alignment (Google Chat platform)
- LiteLLM allows fallback to GPT-4o with zero code changes
- LiteLLM provides automatic retry, token counting, cost tracking

**Fallback**: GPT-4o via OpenAI (configured in LiteLLM router)

---

## ADR-004: PostgreSQL over MongoDB

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Need a database for tasks, users, audit logs.

**Decision**: Use **PostgreSQL 16** with SQLAlchemy async ORM.

**Rationale**:
- Tasks have clear relational structure (user FK, task FK)
- ACID compliance critical for task state transitions
- Native `tsvector` full-text search eliminates need for Elasticsearch
- `pgvector` extension available for semantic search in v2
- JSONB for flexible audit log `changes` column
- Better developer tooling and ORM maturity vs. MongoDB

---

## ADR-005: Redis for Conversation State (LangGraph Checkpointer)

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Need to persist conversation history across multiple Google Chat messages from the same user.

**Decision**: Use **Redis** via LangGraph's `AsyncRedisSaver` for conversation checkpoints.

**Rationale**:
- LangGraph has native Redis checkpointer support
- Sub-millisecond reads/writes for active conversations
- TTL-based auto-expiry (24h) prevents unbounded memory growth
- Redis already used for rate limiting — reduces operational complexity
- Thread-per-user-per-space model maps naturally to Redis keys

**Alternative Considered**: PostgreSQL checkpointer — slower (network round trip + SQL), but more durable. Acceptable trade-off since conversation state is ephemeral.

---

## ADR-006: APScheduler for Proactive Notifications

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Need to send daily briefings and overdue alerts proactively.

**Decision**: Use **APScheduler 3.x** with Redis job store for scheduling.

**Rationale**:
- Python-native, integrates cleanly with FastAPI startup/shutdown
- Redis job store gives distributed lock support (prevents duplicate sends in scaled deployment)
- Supports cron expressions for daily 9 AM briefing
- Sufficient for current scale (< 1000 users)

**Future**: Migrate to Celery Beat if horizontal scaling required.

---

## ADR-007: Soft Delete for Tasks

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: How should task deletion work?

**Decision**: All task deletes are **soft deletes** (`deleted_at = TIMESTAMP`, never `DELETE FROM tasks`).

**Rationale**:
- Audit trail preserved — can recover accidentally deleted tasks
- Required for compliance and accountability in enterprise context
- Audit log + soft delete = full task history
- Dashboard can optionally show deleted tasks to admins
- LLM agents may make mistakes — soft delete adds safety net

---

## ADR-008: Human-in-the-Loop for Destructive Actions

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Should the AI execute all actions immediately?

**Decision**: The **Review & Validation Agent** intercepts DELETE actions and sends a Google Chat confirmation card before execution.

**Rationale**:
- Users can mistype and accidentally delete tasks
- AI may misinterpret "delete old tasks" as a bulk delete
- Google Chat cards support interactive buttons — HITL is native to the platform
- Reduces user trust issues with AI making irreversible changes

**Flow**:
1. User: "Delete the old login task"
2. Bot sends: "⚠️ Are you sure you want to delete *Old login page redesign*? [Delete] [Cancel]"
3. User clicks "Delete" → task soft-deleted

---

## ADR-009: Next.js App Router for Dashboard

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: Frontend framework for the task dashboard.

**Decision**: Use **Next.js 14 with App Router** and **TypeScript**.

**Rationale**:
- App Router provides better server-component support for initial data loading
- TypeScript strict mode for type safety matching backend Pydantic contracts
- TanStack Query for server state caching and auto-refresh
- Vercel deployment ready if needed

---

## ADR-010: Structured Output for Intent Classification

**Date**: 2026-10-07  
**Status**: Accepted  

**Context**: How to reliably extract intent and task fields from natural language?

**Decision**: Use **LangChain's `.with_structured_output()`** with Pydantic models for all structured extractions from LLM.

**Rationale**:
- Eliminates fragile JSON string parsing
- Pydantic validation catches LLM mistakes (wrong types, missing fields)
- Retries on parse failure automatically
- Type-safe — works well with mypy/pyright

```python
class IntentClassification(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    task_context: TaskContext

supervisor_chain = llm.with_structured_output(IntentClassification)
result = await supervisor_chain.ainvoke(messages)
```


---

## ADR-011: Enforce authorization inside agent tools, not only in the REST layer

**Date**: 2026-10-10  **Status**: Accepted

**Context**: Chat reaches the same data as the API. Tools were unscoped, so an employee could search every task, read any task by id, or see team workload simply by asking the bot.

**Decision**: Tools take the caller's identity and apply `auth/rbac.py`; unknown callers fail closed. Tasks the caller cannot see report "not found".

**Consequences**: One rule set for both channels, covered by `tests/test_chat_rbac.py`. System callers (scheduler) omit the identity deliberately.

---

## ADR-012: Never guess a person or a task

**Date**: 2026-10-10  **Status**: Accepted

**Context**: Unknown assignees fell back to the requester, partial name matches took the first hit, and "complete it" completed the user's first active task, all while reporting success.

**Decision**: Ambiguity and absence produce a clarifying question with candidates. Exact matches win over partial ones.

**Consequences**: Occasionally one extra turn; no silent wrong-person assignments or wrong-task completions.

---

## ADR-013: Notification logs record only what really happened

**Date**: 2026-10-10  **Status**: Accepted

**Decision**: `sent` only after a successful Chat API response; `skipped` when the user has no Google Chat account; `failed` with a reason otherwise. All jobs and event notifications share `services.notifications.deliver_with_retry`. DMs use a known DM space or `spaces:findDirectMessage` (the Chat API has no `users/*/messages` endpoint).

---

## ADR-014: Migrations run at container start; models and migrations must not drift

**Date**: 2026-10-10  **Status**: Accepted

**Decision**: The backend entrypoint runs `alembic upgrade head` (RULES 3.1). CI runs `alembic check`; migration 004 aligned historical index names with the models.

---

## ADR-015: Fail closed in production

**Date**: 2026-10-10  **Status**: Accepted

**Decision**: With `ENVIRONMENT=production` the app will not start with a weak or placeholder JWT secret, wildcard CORS, Chat verification off, or verification without an audience. Public registration is off by default and the seed requires an explicit password.

---

## ADR-020: A tool-using agent next to fixed specialists, with hard guardrails

**Date**: 2026-10-12  **Status**: Accepted

**Context**: The specialists run a fixed handler per request type. That is fast, cheap and predictable, but it cannot do "move all of John's overdue tasks to Rahul and make them high priority": the work is open-ended and needs several tool calls whose later steps depend on earlier results.

**Decision**: Add one agent where the LLM plans with function calling (a bounded loop over a small set of tools), and keep the fixed specialists for common requests. The Supervisor chooses: model-classified multi-step requests, and bulk or compound requests that ask for a change, go to the tool agent; everything else keeps the fast path. Safety does not rely on the model behaving: identity is injected, every tool re-checks permissions, deleting is not offered, runs are bounded, and the reply is built from the tools' real results.

**Consequences**: Bigger requests work in Chat and the dashboard. They cost several model calls each (3 to 5), so on a free key they need the fallback chain (ADR-021). If the model is unavailable the fixed specialists still handle simple requests and the tool agent says so honestly.

## ADR-021: A chain of models, each with its own quota

**Date**: 2026-10-12  **Status**: Accepted

**Context**: A free Gemini key allows about 20 requests a day per model, and one multi-step request needs several. A single model runs out within minutes of real use. Quotas are tracked per model.

**Decision**: `DEFAULT_LLM_MODEL` plus `LLM_FALLBACK_MODELS`, tried in order. A model that returns a rate-limit or not-found error rests for the time the provider suggests (capped by `LLM_MAX_BLOCK_SECONDS`), a busy (503) model is skipped for that call, and the next model is tried at once. The circuit breaker only counts a failure when the whole chain fails.

**Consequences**: Daily capacity multiplies by the number of models. Avoid "thinking" models for interactive use (15 seconds or more per answer). A paid key or a self-hosted model removes the limit; the settings do not change.

## ADR-022: Planning, assignment and duplicate checks are algorithms, not prompts

**Date**: 2026-10-12  **Status**: Accepted

**Context**: Smart assignment, week planning and duplicate detection are tempting to hand to the LLM. But they have a right answer that can be computed, people want to know why ("2 open tasks, none late"), and the AI quota is small.

**Decision**: Implement each as a small pure module with tests (`services/duplicates.py`, `services/assignment.py`, `services/week_plan.py`) and let the LLM do what it is good at: understanding the request and writing prose. The same functions serve the REST API, the dashboard, Chat and the AI agent's tools.

**Consequences**: Instant, deterministic and free of AI requests, so they keep working when the AI is down. The trade-off is that the heuristics are fixed (daily limit of 4 tasks, one load formula); they are plain constants meant to be tuned.

## ADR-016: Mission Control dashboard

**Date**: 2026-10-10  **Status**: Accepted

**Context**: The first dashboard mixed two styling systems, hid the agents behind a floating widget on one page, and had no real-time or keyboard story.

**Decision**: Rebuild the frontend on shared design tokens and a small UI kit (docs/DESIGN_MISSION_CONTROL.md): app shell with navigation rail, command palette (`Ctrl+K`), an agent panel available on every page with live run traces, drag-and-drop board with optimistic updates, URL-synced filters, readable audit trail. Server state stays in TanStack Query; the REST contract is unchanged apart from additions.

**Consequences**: Routes changed (`/analytics` is now `/insights`, `/settings` is split into `/admin` and `/profile`). Dashboard behaviour is covered by Vitest and Playwright suites.

---

## ADR-017: Live updates are hints over SSE, published from a commit hook

**Date**: 2026-10-11  **Status**: Accepted

**Context**: Tasks change from the dashboard, Google Chat and the scheduler; the dashboard only polled every 15 seconds.

**Decision**: A SQLAlchemy `after_commit` hook publishes `{topic, task_id}` for any committed change to tasks, comments or attachments, so no code path can forget to publish and rolled-back work never publishes. The stream carries no task data; clients invalidate TanStack Query caches and refetch through the authorised REST API. The stream is authenticated with the bearer token and does not hold a database connection while open. SSE was chosen over WebSockets because traffic is one-way, it works through ordinary proxies, and reconnection is trivial.

**Consequences**: One process per deployment is exact; multiple workers need a shared bus (documented). Polling stays as the fallback, so a broken stream degrades to slower updates.

## ADR-018: Attachments on local disk with an allow-list

**Date**: 2026-10-11  **Status**: Accepted

**Context**: Users need to attach documents. Uploads are a classic source of vulnerabilities.

**Decision**: Files are stored under random names on a volume; the client's file name is display metadata only. Only an extension allow-list is accepted (no HTML, SVG, scripts or executables) and the content type is derived from it, never trusted from the client. Size is enforced while streaming and partial files are removed. Downloads are always `attachment` with `nosniff`, authorised by the task's view permission; uploads need edit permission.

**Consequences**: No virus scanning and no object storage yet; both are documented upgrade paths. Backups must include the volume.

## ADR-019: Fail soft around the LLM and Google's 30 second limit

**Date**: 2026-10-11  **Status**: Accepted

**Context**: Google Chat shows "not responding" if the webhook takes over 30 seconds. LLM calls had no per-call timeout, and a quota outage would make every message slow before falling back.

**Decision**: Per-attempt LLM timeout, two attempts, a circuit breaker that skips the provider for a cooldown after repeated failures, and an agent deadline (22 seconds) shorter than Google's limit that returns an apology instead of silence.

**Consequences**: During an LLM outage the bot answers from the rule-based classifier immediately rather than slowly; behaviour is covered by `tests/test_resilience.py`.
