# TOOLS.md — Tool Contracts
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.1.0  
**Last Updated:** 2026-10-10

---

## 1. Overview

Tools are Python functions decorated with `@tool` (LangChain) that agents call to perform deterministic operations. All tools interact with the database through the Deterministic Tool Gateway (SQLAlchemy async session).

### Permission model (as built)

Tools never raise: failures return `ToolResult(success=False, error=...)`. Tools that read or change data accept the caller's identity so chat obeys the same rules as the REST API (`auth/rbac.py`):

| Tool | Identity parameter | Rule |
|---|---|---|
| `search_tasks` | `viewer_id` | Employees see only tasks they created or are assigned |
| `get_task_by_id` | `viewer_id` | Not visible reports the same "not found" as a missing task |
| `get_task_stats` | `viewer_id` | Employees get their own scope |
| `get_team_workload` | `viewer_id` | Managers and admins only |
| `create_task` | `created_by_id` | Unknown or inactive caller refused; employees may only assign to themselves |
| `update_task` | `updated_by_id` | Object-level check; employees cannot reassign |
| `complete_task` | `completed_by_id` | Object-level check; idempotent; cancelled tasks refused |
| `delete_task` | `deleted_by_id` | Managers and admins only (and only after confirmation by the Review agent) |

Omitting `viewer_id` means a trusted system caller (for example the scheduler computing team statistics); agents always pass it.

Assignee names are resolved by `tools.base.resolve_user_reference`: one clear match is used, no match or several matches return an error message the agent relays as a question.

### Tool Naming Convention
`{verb}_{noun}` — e.g., `create_task`, `get_user_tasks`, `search_tasks`

### Tool Response Format
All tools return a `ToolResult` TypedDict:
```python
class ToolResult(TypedDict):
    success: bool
    data: Any          # The returned data
    error: str | None  # Error message if success=False
    count: int | None  # Row count for list operations
```

---

## 2. Task Tools

### 2.1 `create_task`
**Description**: Creates a new task in the database.

**Input Schema**:
```python
class CreateTaskInput(BaseModel):
    title: str                           # Required, max 255 chars
    description: str | None = None
    priority: Literal["LOW","MEDIUM","HIGH","CRITICAL"] = "MEDIUM"
    assignee_id: str | None = None       # UUID of assignee
    assignee_name: str | None = None     # If ID unknown, resolve by name
    due_date: date | None = None
    created_by_id: str                   # UUID of creator (from state.user_id)
    tags: list[str] = []
```

**Output**: `ToolResult` with `data = Task` (full task object)

**Side Effects**: 
- INSERT into `tasks` table
- INSERT into `task_audit_logs` (action="CREATED")
- Trigger duplicate check (warn if similar task exists)

**Example**:
```python
result = create_task.invoke({
    "title": "Deploy frontend",
    "priority": "HIGH",
    "assignee_name": "John",
    "due_date": "2026-10-10",
    "created_by_id": "user-uuid"
})
```

---

### 2.2 `get_task_by_id`
**Description**: Fetches a single task by UUID.

**Input Schema**:
```python
class GetTaskInput(BaseModel):
    task_id: str    # UUID
```

**Output**: `ToolResult` with `data = Task | None`

**Notes**: Returns None (not 404) if not found — agent handles messaging.

---

### 2.3 `update_task`
**Description**: Partially updates a task. Only provided fields are updated.

**Input Schema**:
```python
class UpdateTaskInput(BaseModel):
    task_id: str
    title: str | None = None
    description: str | None = None
    priority: Literal["LOW","MEDIUM","HIGH","CRITICAL"] | None = None
    assignee_id: str | None = None
    due_date: date | None = None
    status: Literal["TODO","IN_PROGRESS","REVIEW","DONE","CANCELLED"] | None = None
    tags: list[str] | None = None
    updated_by_id: str                   # For audit log
```

**Output**: `ToolResult` with `data = Task` (updated task)

**Side Effects**:
- UPDATE `tasks` table (only changed fields)
- INSERT into `task_audit_logs` with diff

---

### 2.4 `complete_task`
**Description**: Marks a task as DONE with completion timestamp.

**Input Schema**:
```python
class CompleteTaskInput(BaseModel):
    task_id: str
    completed_by_id: str
    completion_note: str | None = None
```

**Output**: `ToolResult` with `data = Task`

**Side Effects**:
- UPDATE `tasks` SET status=DONE, completed_at=NOW()
- INSERT audit log

---

### 2.5 `delete_task`
**Description**: Soft-deletes a task (sets deleted_at, not removed from DB).

**Input Schema**:
```python
class DeleteTaskInput(BaseModel):
    task_id: str
    deleted_by_id: str
    reason: str | None = None
```

**Output**: `ToolResult` with `data = {"deleted_id": task_id}`

**IMPORTANT**: Only called after Review Agent confirmation.

---

### 2.6 `search_tasks`
**Description**: Full-text search with optional filters.

**Input Schema**:
```python
class SearchTasksInput(BaseModel):
    query: str | None = None            # Full-text search term
    assignee_id: str | None = None
    status: list[str] | None = None     # e.g., ["TODO", "IN_PROGRESS"]
    priority: list[str] | None = None
    due_before: date | None = None
    due_after: date | None = None
    created_by_id: str | None = None
    include_completed: bool = False
    limit: int = 20
    offset: int = 0
```

**Output**: `ToolResult` with `data = list[Task]`, `count = total_count`

**Implementation**: Uses PostgreSQL `tsvector` for full-text search + filtered WHERE clauses.

---

### 2.7 `get_user_tasks`
**Description**: Get all tasks for a specific user with status filters.

**Input Schema**:
```python
class GetUserTasksInput(BaseModel):
    user_id: str
    status: list[str] = ["TODO", "IN_PROGRESS", "REVIEW"]
    limit: int = 50
```

**Output**: `ToolResult` with `data = list[Task]`

---

### 2.8 `get_overdue_tasks`
**Description**: Get tasks where due_date < today AND status not in [DONE, CANCELLED].

**Input Schema**:
```python
class GetOverdueTasksInput(BaseModel):
    user_id: str | None = None    # If None, gets all users' overdue tasks
    limit: int = 50
```

**Output**: `ToolResult` with `data = list[Task]` (each has `days_overdue` computed field)

---

### 2.9 `get_tasks_due_today`
**Description**: Get tasks due today for a user.

**Input Schema**:
```python
class GetTasksDueTodayInput(BaseModel):
    user_id: str
```

**Output**: `ToolResult` with `data = list[Task]`

---

## 3. User Tools

### 3.1 `get_user_by_name`
**Description**: Resolves a user by first name, last name, or display name (partial match).

**Input Schema**:
```python
class GetUserByNameInput(BaseModel):
    name: str    # e.g., "John", "rahul", "John Doe"
```

**Output**: `ToolResult` with `data = list[User]` (may return multiple matches)

**Notes**: Returns all partial matches — agent should pick best match or ask for clarification if ambiguous.

---

### 3.2 `get_all_users`
**Description**: Get all registered users in the system.

**Output**: `ToolResult` with `data = list[User]`

---

### 3.3 `get_team_workload`
**Description**: Returns task count per user grouped by status.

**Output**: 
```python
ToolResult(data=[
    {"user": User, "task_count": 5, "overdue_count": 1, "high_priority_count": 2},
    ...
])
```

---

## 4. Analytics Tools

### 4.1 `get_task_stats`
**Description**: Returns aggregate statistics for a user or all users.

**Input Schema**:
```python
class GetTaskStatsInput(BaseModel):
    user_id: str | None = None    # None = all users
    date_from: date | None = None
    date_to: date | None = None
```

**Output**:
```python
{
    "total_tasks": 42,
    "completed_tasks": 30,
    "overdue_tasks": 5,
    "completion_rate": 0.71,
    "avg_completion_days": 3.2,
    "tasks_by_priority": {"HIGH": 10, "MEDIUM": 25, "LOW": 7},
    "tasks_by_status": {"TODO": 5, "IN_PROGRESS": 7, "DONE": 30}
}
```

---

## 5. Formatting Tools

### 5.1 `format_task_card`
**Description**: Formats a task as a Google Chat card JSON payload.

**Input**: `Task` object  
**Output**: `dict` — Google Chat card JSON

**Example Output**:
```json
{
  "cardsV2": [{
    "card": {
      "header": {"title": "Deploy Frontend", "subtitle": "Task #42 • HIGH Priority"},
      "sections": [{
        "widgets": [
          {"decoratedText": {"topLabel": "Assignee", "text": "John Doe"}},
          {"decoratedText": {"topLabel": "Due Date", "text": "Oct 10, 2026"}},
          {"decoratedText": {"topLabel": "Status", "text": "IN_PROGRESS"}}
        ]
      }],
      "fixedFooter": {
        "primaryButton": {"text": "Mark Complete", "onClick": {"action": {"function": "complete_task", "parameters": [{"key": "task_id", "value": "uuid"}]}}}
      }
    }
  }]
}
```

---

## 6. Tool Registry

All tools registered per agent:

```python
TASK_AGENT_TOOLS = [
    create_task, get_task_by_id, update_task, complete_task,
    delete_task, search_tasks, get_user_tasks, get_user_by_name,
    format_task_card
]

PLANNER_AGENT_TOOLS = [
    get_user_tasks, get_overdue_tasks, get_tasks_due_today, 
    get_tasks_due_this_week, get_task_stats
]

RECOMMENDATION_AGENT_TOOLS = [
    get_overdue_tasks, search_tasks, get_task_stats, get_team_workload
]

REVIEW_AGENT_TOOLS = [
    get_task_by_id, get_user_by_name
]
```
