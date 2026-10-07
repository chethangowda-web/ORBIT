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
