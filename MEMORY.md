# MEMORY.md — State & Memory Strategy
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Last Updated:** 2026-10-07

---

## 1. Memory Architecture Overview

ORBIT uses a **layered memory strategy** — short-term conversation memory in Redis, long-term preferences and patterns in PostgreSQL.

```
┌─────────────────────────────────────────────────────┐
│                  MEMORY LAYERS                       │
│                                                       │
│  Layer 1: Working Memory (AgentState)                │
│  ─ In-memory Python dict during single request       │
│  ─ Wiped after response is sent                      │
│                                                       │
│  Layer 2: Short-term Memory (Redis)                  │
│  ─ Conversation history (last 20 messages)           │
│  ─ TTL: 24 hours per thread                          │
│  ─ Key: orbit:thread:{space_id}:{user_id}            │
│                                                       │
│  Layer 3: Long-term Memory (PostgreSQL)              │
│  ─ User preferences                                  │
│  ─ Notification history                              │
│  ─ Task audit trail                                  │
│  ─ No TTL — permanent                               │
└─────────────────────────────────────────────────────┘
```

---

## 2. Conversation Memory (Layer 2)

### 2.1 LangGraph Checkpointer

ORBIT persists conversation state with `AsyncRedisCheckpointer` (`backend/agents/memory_agent.py`), a small LangGraph `BaseCheckpointSaver` over `redis.asyncio` with a 24 hour TTL. If Redis is unreachable it falls back to the in-memory saver outside production (see `CHECKPOINTER_BACKEND` and `ALLOW_IN_MEMORY_CHECKPOINTER_FALLBACK`).

```python
checkpointer = AsyncRedisCheckpointer(redis_client, ttl=86400)
graph = workflow.compile(checkpointer=checkpointer)
```

### 2.2 Thread ID

Each user-per-space has a unique thread:
```python
thread_id = f"{space_id}:{user_id}"
# Example: "spaces/AAA123:users/BBB456"

# Passed to graph invocation:
config = {"configurable": {"thread_id": thread_id}}
result = await graph.ainvoke(state, config=config)
```

### 2.3 What Gets Stored

The checkpointer stores the **full AgentState** after each invocation:
```python
{
    "messages": [...],            # Full LangChain message history
    "tool_calls_made": [...],     # Tools called in session
    "task_context": {...},        # Last extracted task context
    "referenced_task_id": "uuid" # Last referenced task
}
```

### 2.4 Context Resolution

The Memory Agent resolves entity references from conversation history:

**Example**:
```
Turn 1 - User: "Create a task to deploy frontend for John by Friday"
Turn 1 - Bot:  "Created task #42: Deploy frontend (assigned to John Doe)"

Turn 2 - User: "Mark it as high priority"
```

Resolution:
```python
def resolve_references(message: str, state: AgentState) -> dict:
    # "it" → look at last assistant message → find task_id = "42"
    # Returns: {"referenced_task_id": "42", "update_field": "priority", "value": "HIGH"}
    
    prompt = f"""
    Given the conversation history and the new user message, resolve any references:
    - "it", "that task", "the task" → find the most recently mentioned task ID
    - "him", "her", "them" → find the most recently mentioned user name
    
    History: {format_history(state['messages'][-6:])}
    New message: {message}
    
    Return: {{"task_id": "...", "user_name": "..."}} or null if no reference
    """
    # Uses Gemini Flash for speed (small context window task)
```

### 2.5 Redis Key Strategy

```
orbit:checkpoint:{thread}:{ns}:{id}   → LangGraph checkpoint
orbit:threads:{thread}:{ns}           → index of checkpoints for a thread
orbit:ratelimit:login:{ip}:{email}    → failed sign-in counter (expires with the window)
orbit:lock:scheduler:{job_name}       → scheduler job lock (5 minute TTL)

(No JWT blacklist exists: tokens are stateless; see OPERATIONS.md section 8.)
```

### 2.6 TTL Strategy

| Key Pattern | TTL | Reason |
|-------------|-----|--------|
| `orbit:thread:*` | 24 hours | Daily conversation window |
| `orbit:rate:*` | 60 seconds | Rate limit window |
| `orbit:session:*` | 24 hours | JWT lifetime |
| `orbit:lock:*` | 5 minutes | Scheduler job timeout |

---

## 3. Long-term Memory (Layer 3 — PostgreSQL)

### 3.1 User Preferences

Stored in `user_preferences` table as key-value pairs.

**Loading preferences**:
```python
async def get_user_preferences(user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    prefs = result.scalars().all()
    return {p.key: p.value for p in prefs}
```

**Setting preferences** (via natural language):
> "Stop sending me daily briefings"
- Intent: UPDATE_PREFERENCE
- Supervisor extracts: `{"key": "daily_briefing", "value": "false"}`
- Task Agent calls `update_user_preference` tool

### 3.2 Notification History

The `notification_logs` table tracks what was sent to prevent duplicates:

```python
async def should_send_briefing(user_id: str, db: AsyncSession) -> bool:
    """Check if we already sent a briefing today."""
    today = datetime.utcnow().date()
    result = await db.execute(
        select(NotificationLog).where(
            NotificationLog.user_id == user_id,
            NotificationLog.type == "daily_briefing",
            func.date(NotificationLog.sent_at) == today,
            NotificationLog.status == "sent"
        )
    )
    return result.scalar() is None  # True = should send
```

---

## 4. Working Memory (Layer 1 — AgentState)

### 4.1 State Initialization

At the start of each request:
```python
async def initialize_state(event: GoogleChatEvent, user: User) -> AgentState:
    return AgentState(
        user_id=str(user.id),
        google_user_id=event.sender.name,
        space_id=event.space.name,
        thread_id=f"{event.space.name}:{event.sender.name}",
        raw_message=event.message.text,
        intent="",
        confidence=0.0,
        active_agent="",
        messages=[],          # Loaded by Memory Agent from Redis
        task_context={},
        referenced_task_id=None,
        needs_confirmation=False,
        confirmed=False,
        response="",
        response_type="text",
        card_data=None,
        tool_calls_made=[],
        error=None,
        retry_count=0
    )
```

### 4.2 Message History Management

After loading from Redis:
```python
# Trim to last 20 messages to stay within context window
MAX_HISTORY = 20
state["messages"] = state["messages"][-MAX_HISTORY:]

# Always prepend system message
state["messages"].insert(0, SystemMessage(content=SYSTEM_PROMPT))

# Append new user message
state["messages"].append(HumanMessage(content=state["raw_message"]))
```

---

## 5. Memory Failure Handling

| Scenario | Behavior |
|----------|---------|
| Redis unavailable | Start fresh state (no history), log warning |
| Checkpoint corrupted | Clear checkpoint, start fresh, notify user |
| Context too long | Trim to last 10 messages, summarize older context |
| DB unavailable | Return error to user, do not process |

### Context Summarization (for long conversations)
```python
async def summarize_context(messages: list[BaseMessage]) -> str:
    """Compress old messages into a summary to save tokens."""
    # Keep last 5 messages verbatim
    # Summarize everything older
    old_messages = messages[:-5]
    prompt = f"Summarize this conversation context in 3 sentences: {old_messages}"
    summary = await llm.ainvoke(prompt)
    return summary.content
```

---

## 6. Multi-turn Conversation Examples

### Example 1: Reference resolution
```
User: "Create a task to test the payment API, assign to Sarah, due Monday"
Bot:  "✅ Created: Test payment API (Task #55) assigned to Sarah Chen, due Oct 13"

User: "Actually make it high priority"
# Memory resolves: task_id=55, field=priority, value=HIGH
Bot:  "✅ Updated Task #55 priority to HIGH"

User: "And move the deadline to Wednesday"
# Memory resolves: task_id=55, field=due_date, value=Oct 15
Bot:  "✅ Updated Task #55 due date to Oct 15"
```

### Example 2: Preference learning
```
User: "Don't send me morning briefings on weekends"
# Long-term memory: user_preferences["weekend_briefing"] = false
Bot:  "Got it! I'll skip morning briefings on weekends 🗓️"
```
