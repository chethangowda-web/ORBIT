# AGENTS.md — Agent Responsibilities & Contracts
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.1.0  
**Last Updated:** 2026-10-10

> Source of truth: `backend/agents/`. Differences from the first design are summarised in section 7.

---

## 1. Agent Overview

ORBIT uses a **Supervisor Pattern** implemented with LangGraph. All agents share a common `AgentState` and communicate through it. The Supervisor routes requests; specialist agents execute.

```
┌───────────────────────────────────────────────────────┐
│                  SUPERVISOR AGENT                      │
│  (Entry point for all user messages)                   │
└──┬────────────┬────────────┬────────────┬─────────────┘
   │            │            │            │
   ▼            ▼            ▼            ▼
┌──────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐
│ TASK │  │ PLANNER │  │ RECOMMEND│  │ REVIEW &     │
│AGENT │  │  AGENT  │  │  AGENT   │  │ VALIDATION   │
└──────┘  └─────────┘  └──────────┘  └──────────────┘
   └────────────────────────┘
              │ All agents share
              ▼
        ┌────────────┐
        │   MEMORY   │
        │   AGENT    │
        └────────────┘
```

---

## 2. Shared State Contract

```python
from typing import TypedDict, Optional
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # === INPUT ===
    user_id: str                    # Internal user UUID
    google_user_id: str             # Google Chat user ID
    space_id: str                   # Google Chat space ID
    thread_id: str                  # Conversation thread ID (space_id:user_id)
    raw_message: str                # Original user message
    
    # === ROUTING ===
    intent: str                     # Classified intent enum
    confidence: float               # Intent classification confidence
    active_agent: str               # Which specialist agent is running
    
    # === CONVERSATION HISTORY ===
    messages: list[BaseMessage]     # Full LangChain message history
    
    # === EXTRACTED CONTEXT ===
    task_context: dict              # Extracted task fields {title, assignee, priority, due_date}
    referenced_task_id: Optional[str]  # If user referenced a specific task
    
    # === CONTROL FLOW ===
    needs_confirmation: bool        # HITL — requires user confirmation
    confirmed: bool                 # User confirmed the action
    
    # === OUTPUT ===
    response: str                   # Final response text for Google Chat
    response_type: str              # "text" | "card" | "confirmation_dialog"
    card_data: Optional[dict]       # Google Chat card payload
    tool_calls_made: list[str]      # Audit log of tools called
    
    # === ERROR ===
    error: Optional[str]            # Error message if agent failed
    retry_count: int                # Number of retries attempted
```

---

## 3. Intent Enum

```python
class Intent(str, Enum):
    CREATE_TASK = "CREATE_TASK"
    UPDATE_TASK = "UPDATE_TASK"
    DELETE_TASK = "DELETE_TASK"
    COMPLETE_TASK = "COMPLETE_TASK"
    GET_MY_TASKS = "GET_MY_TASKS"
    GET_OVERDUE_TASKS = "GET_OVERDUE_TASKS"
    SEARCH_TASKS = "SEARCH_TASKS"
    GET_TASK_DETAIL = "GET_TASK_DETAIL"
    PLAN_DAY = "PLAN_DAY"
    GET_RECOMMENDATIONS = "GET_RECOMMENDATIONS"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"
```

---

## 4. Agent Contracts

---

### 4.1 Supervisor Agent

**File**: `backend/agents/supervisor.py`

**Responsibility**:
- Entry point for all Google Chat messages
- Classifies user intent using LLM + structured output
- Routes to appropriate specialist agent
- Manages conversation history loading/saving
- Handles UNKNOWN intents gracefully

**Input**: Raw user message + user_id + space_id  
**Output**: Populated AgentState with `intent` and routing decision

**System Prompt**:
```
You are ORBIT's intelligent router. Analyze the user message and classify it 
into one of the following intents: [CREATE_TASK, UPDATE_TASK, DELETE_TASK, 
COMPLETE_TASK, GET_MY_TASKS, GET_OVERDUE_TASKS, SEARCH_TASKS, GET_TASK_DETAIL, 
PLAN_DAY, GET_RECOMMENDATIONS, HELP, UNKNOWN].

Also extract any task context from the message:
- task_title: string
- assignee_name: string (if mentioned)
- priority: LOW|MEDIUM|HIGH|CRITICAL (if mentioned)
- due_date: ISO date string (if mentioned, resolve relative dates like "Friday")
- task_id: string (if user references a specific task number)

Respond with structured JSON only.
```

**Tools**: None (pure classification)

**LangGraph Node**:
```python
def supervisor_node(state: AgentState) -> AgentState:
    # 1. Load conversation history from Memory Agent
    # 2. Classify intent via LLM
    # 3. Extract task_context
    # 4. Set state.intent and state.active_agent
    # 5. Return updated state
```

**Routing Logic**:
```python
ROUTING_MAP = {
    Intent.CREATE_TASK: "task_agent",
    Intent.UPDATE_TASK: "task_agent",
    Intent.DELETE_TASK: "review_agent",   # Always validate deletes
    Intent.COMPLETE_TASK: "task_agent",
    Intent.GET_MY_TASKS: "task_agent",
    Intent.GET_OVERDUE_TASKS: "recommendation_agent",
    Intent.SEARCH_TASKS: "task_agent",
    Intent.PLAN_DAY: "planner_agent",
    Intent.GET_RECOMMENDATIONS: "recommendation_agent",
    Intent.HELP: "task_agent",            # Returns help text
    Intent.UNKNOWN: "task_agent",         # Returns clarification prompt
}
```

---

### 4.2 Task Management Agent

**File**: `backend/agents/task_agent.py`

**Responsibility**:
- Executes all task CRUD operations
- Uses tools to interact with PostgreSQL via Deterministic Tool Gateway
- Formats responses as Google Chat cards

**Input**: AgentState with intent + task_context  
**Output**: AgentState with response populated

**System Prompt**:
```
You are ORBIT's Task Management Agent. You handle task creation, retrieval, 
updates, and completion. Use the available tools to perform the requested action.

Always confirm what you did by summarizing the action taken. Be concise.
If a task title is ambiguous, use the search tool to find the best match.
```

**Tools**:
| Tool | Description |
|------|-------------|
| `create_task` | Create a new task with extracted fields |
| `get_task_by_id` | Get task by UUID |
| `search_tasks` | Full-text + filter search |
| `update_task` | Partial update of any task field |
| `complete_task` | Mark task as DONE |
| `delete_task` | Soft-delete a task |
| `get_user_tasks` | Get all tasks for a user with optional filters |
| `get_users` | Look up users by name for assignment |
| `format_task_card` | Format task as Google Chat card |

**Error Handling**: If tool call fails, retry once, then return graceful error message.

---

### 4.3 Planner Agent

**File**: `backend/agents/planner_agent.py`

**Responsibility**:
- Generates daily task plans for users
- Prioritizes tasks based on deadline, priority, and workload
- Provides reasoning for recommended order
- Used both reactively (user asks "what to focus on?") and proactively (daily briefing)

**Input**: AgentState with user_id  
**Output**: Formatted daily plan with top 3–5 tasks + reasoning

**System Prompt**:
```
You are ORBIT's Planning Agent. Analyze the user's task list and generate an 
intelligent daily plan. Consider:
1. Tasks due today (CRITICAL)
2. Overdue tasks (HIGH urgency)
3. HIGH priority tasks due this week
4. Task dependencies (if mentioned in description)

Output a clear plan with:
- Top 5 tasks to focus on, ranked
- Reasoning for each selection
- Estimated focus time if possible
- Any warnings about overdue items

Keep the response actionable and concise.
```

**Tools**:
| Tool | Description |
|------|-------------|
| `get_user_tasks` | Get all non-completed tasks |
| `get_overdue_tasks` | Get tasks past due date |
| `get_tasks_due_today` | Get tasks due today |
| `get_tasks_due_this_week` | Get tasks due this week |

---

### 4.4 Recommendation Agent

**File**: `backend/agents/recommendation_agent.py`

**Responsibility**:
- Detects overdue tasks and generates alerts
- Identifies duplicate or similar tasks
- Provides productivity insights
- Generates weekly summary reports
- Used by Autonomous Scheduler for proactive notifications

**Input**: AgentState with user_id (or all users for scheduled runs)  
**Output**: Insights, recommendations, alert messages

**System Prompt**:
```
You are ORBIT's Recommendation Agent. Analyze task data to provide intelligent 
insights. You can:
1. Identify overdue tasks and suggest urgency
2. Detect potential duplicate tasks (similar titles/descriptions)
3. Highlight users with high task load
4. Generate productivity summaries

Be specific, actionable, and concise.
```

**Tools**:
| Tool | Description |
|------|-------------|
| `get_overdue_tasks` | Tasks past due date, not done |
| `search_tasks` | Semantic/keyword search for duplicates |
| `get_task_stats` | Completion rate, average time, etc. |
| `get_team_workload` | Tasks per user distribution |

---

### 4.5 Review & Validation Agent

**File**: `backend/agents/review_agent.py`

**Responsibility**:
- Intercepts destructive actions (DELETE, bulk updates)
- Validates business rules before execution
- Implements Human-in-the-Loop (HITL) for dangerous actions
- Sends confirmation dialog via Google Chat
- Checks RBAC (can this user do this action?)

**Input**: AgentState with pending action + task_context  
**Output**: AgentState with confirmed=True/False, or confirmation dialog sent

**Rules Enforced**:
| Rule | Action |
|------|--------|
| Delete task owned by another user | Require MANAGER role |
| Bulk delete (>5 tasks) | Always require HITL confirmation |
| Reassign task not owned by user | Require MANAGER role |
| Complete task not assigned to user | Allow (any team member can complete) |
| Set priority CRITICAL | Log extra audit entry |

**HITL Flow**:
```
1. Review Agent determines action needs confirmation
2. Sets state.needs_confirmation = True
3. Returns confirmation card to Google Chat
4. User clicks "Confirm" or "Cancel" button
5. Webhook receives button click event
6. If confirmed: execute original action
7. If cancelled: return cancellation message
```

---

### 4.6 Memory Agent

**File**: `backend/agents/memory_agent.py`

**Responsibility**:
- Manages persistent conversation state using LangGraph Redis checkpointer
- Loads conversation history before each request
- Saves updated state after each request
- Manages user preference storage
- Resolves entities from history (e.g., "that task" → task_id from previous turn)

**Storage**:
- **Short-term**: Redis (conversation history, last 20 messages, TTL 24h)
- **Long-term**: PostgreSQL (user preferences, frequent task patterns)

**Thread ID Format**: `{space_id}:{user_id}` — unique per user per chat space

**Context Resolution**:
```python
def resolve_context(message: str, history: list[BaseMessage]) -> dict:
    """
    Resolves pronouns and references from conversation history.
    "that task" → look at previous assistant message for task_id
    "John" → check if John was mentioned in last 5 turns
    """
```

**Preference Storage** (PostgreSQL `user_preferences` table):
```json
{
  "notification_time": "09:00",
  "timezone": "Asia/Kolkata",
  "daily_briefing": true,
  "preferred_view": "list"
}
```

---

## 5. Agent Graph Definition

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("task_agent", task_agent_node)
workflow.add_node("planner_agent", planner_agent_node)
workflow.add_node("recommendation_agent", recommendation_agent_node)
workflow.add_node("review_agent", review_agent_node)
workflow.add_node("memory_save", memory_save_node)

# Entry point
workflow.set_entry_point("supervisor")

# Conditional routing from supervisor
workflow.add_conditional_edges(
    "supervisor",
    route_to_agent,   # returns agent name string
    {
        "task_agent": "task_agent",
        "planner_agent": "planner_agent",
        "recommendation_agent": "recommendation_agent",
        "review_agent": "review_agent",
    }
)

# After specialist agent, always save memory
workflow.add_edge("task_agent", "memory_save")
workflow.add_edge("planner_agent", "memory_save")
workflow.add_edge("recommendation_agent", "memory_save")

# Review agent can route to task_agent (if confirmed) or memory_save (if denied)
workflow.add_conditional_edges(
    "review_agent",
    check_confirmation,
    {"confirmed": "task_agent", "denied": "memory_save"}
)

workflow.add_edge("memory_save", END)

# Compile with Redis checkpointer
app = workflow.compile(checkpointer=AsyncRedisSaver(redis_client))
```

---

## 7. As built: behaviours and safety rules

**Graph.** `START -> supervisor -> {task_agent | planner_agent | recommendation_agent | review_agent} -> END`. There is no separate `memory_save` node: the Redis checkpointer persists state after every node, and the review agent performs the confirmed delete itself rather than routing back to the task agent.

**Never guess.** The agents ask instead of acting when the target is unclear:
- Unknown assignee: "I could not find a team member matching 'X'." (the task is **not** silently assigned to the requester).
- Ambiguous assignee (two people match "Joe"): lists the candidates and asks which one. Exact name or email beats partial matches; a single clear first-name match wins.
- "Complete it" with no referenced task, or a title matching several tasks: asks which one. It never completes "the first active task".

**Caller-scoped tools.** The agents pass the caller's id to the tools:
- `search_tasks`, `get_task_by_id`: employees only see tasks they created or are assigned. A task they cannot see reports "not found", the same as a missing one.
- `get_team_workload`: managers and admins only. The recommendation agent falls back to the caller's own numbers for everyone else.
- `get_task_stats`: employees get their own scope; same rules as `GET /analytics/stats`.
- `create_task`, `update_task`, `complete_task`, `delete_task` fail closed: an unknown or inactive caller is refused, and employees cannot assign or reassign to others.

**Delete flow (human-in-the-loop).**
1. Non-managers are refused immediately ("Only managers and admins can delete tasks"), before any task title is revealed.
2. Managers get a confirmation (card in Chat, Confirm/Cancel in the dashboard). The pending action is bound to user id and thread, marked `CONSUMED` on use, and cannot be replayed or confirmed from another session.
3. Card buttons map only to known actions (`confirm_delete_task`, `confirm_action`, `cancel_action`, `cancel`, `complete_task`); anything else is ignored rather than forwarded to the agent as text.

**Dates.** Relative dates ("Friday", "tomorrow") resolve in `APP_TIMEZONE`, not UTC.

**Workflow visibility.** Every run records its steps in order: the Supervisor (intent, confidence, and whether the intent came from the LLM, the built-in rules, or a yes/cancel answer), then the specialist agent with the tools it called and the time each step took. The dashboard draws this under every reply in the agent panel and on the Agent workflow screen, which also shows per-agent run counts. The Admin screen's Integrations tab shows whether Google Chat, the AI model and email are connected and being used.

**Conversation state.** Each turn starts clean: a new request clears any pending confirmation, the previous reply and the "cancelled" marker, so a later "yes" cannot answer an old delete prompt. A message that names a task never inherits the previous one; one that names none ("mark as done", "move that deadline to Friday") means the task just discussed. Deleting needs an explicit reference on top of the confirmation, which expires after 10 minutes.

**LLM use.** With no API key the supervisor uses the deterministic classifier; with a key it uses structured output and falls back to the classifier after three failed attempts. Specialist replies are grounded in tool data and fall back to deterministic text if the model fails.

## 6. Proactive Agent Flows

### 6.1 Daily Briefing Flow (9:00 AM)
```
APScheduler fires
  → Load all users with daily_briefing=True from DB
  → For each user:
      → Invoke PlannerAgent with user_id (no chat message)
      → PlannerAgent generates briefing using tools
      → GoogleChatService.send_dm(user.google_id, briefing)
      → Log delivery in DB
```

### 6.2 Overdue Follow-up Flow (6:00 PM)
```
APScheduler fires
  → Load tasks where due_date < today AND status != DONE
  → Group by assignee
  → For each user with overdue tasks:
      → RecommendationAgent generates overdue summary
      → GoogleChatService.send_dm(user.google_id, summary)
```
