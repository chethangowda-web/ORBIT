# API.md — Backend API Contracts
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000/api`  
**Auth:** Bearer JWT in Authorization header

---

## 1. Authentication

### POST `/auth/token`
Get JWT token for dashboard access.

**Request**:
```json
{ "email": "user@example.com", "password": "secret" }
```

**Response**:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": { "id": "uuid", "name": "John Doe", "role": "employee" }
  }
}
```

---

## 2. Google Chat Webhook

### POST `/chat/webhook`
Receives all Google Chat events. Must return within 30s.

**Headers**:
- `X-Goog-Signature`: HMAC-SHA256 signature for verification

**Request Body** (Google Chat event format):
```json
{
  "type": "MESSAGE",
  "eventTime": "2026-10-07T09:00:00Z",
  "message": {
    "name": "spaces/SPACE_ID/messages/MSG_ID",
    "sender": {
      "name": "users/USER_GOOGLE_ID",
      "displayName": "John Doe",
      "email": "john@example.com"
    },
    "text": "Create a high priority task to deploy frontend by Friday",
    "space": { "name": "spaces/SPACE_ID", "type": "DM" }
  }
}
```

**Response**: Google Chat message format
```json
{
  "text": "✅ Task created: *Deploy frontend* (#42)\nPriority: HIGH | Due: Friday, Oct 10"
}
```

**Event Types Handled**:
| Type | Description |
|------|-------------|
| `MESSAGE` | New user message |
| `CARD_CLICKED` | User clicked button in card (HITL confirmation) |
| `ADDED_TO_SPACE` | Bot added to space (send welcome message) |
| `REMOVED_FROM_SPACE` | Bot removed |

---

## 3. Tasks API

### GET `/tasks`
List tasks with filters and pagination.

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string[] | all | Filter by status |
| `priority` | string[] | all | Filter by priority |
| `assignee_id` | UUID | - | Filter by assignee |
| `created_by_id` | UUID | - | Filter by creator |
| `due_before` | date | - | Tasks due before this date |
| `due_after` | date | - | Tasks due after this date |
| `q` | string | - | Full-text search query |
| `include_completed` | bool | false | Include DONE/CANCELLED |
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |
| `sort_by` | string | due_date | Sort field |
| `sort_dir` | asc/desc | asc | Sort direction |

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "title": "Deploy frontend",
      "description": "Deploy to production server",
      "status": "IN_PROGRESS",
      "priority": "HIGH",
      "assignee": { "id": "uuid", "name": "John Doe", "email": "john@example.com" },
      "created_by": { "id": "uuid", "name": "Manager" },
      "due_date": "2026-10-10",
      "completed_at": null,
      "tags": ["deployment", "frontend"],
      "created_at": "2026-10-07T09:00:00Z",
      "updated_at": "2026-10-07T10:00:00Z",
      "days_overdue": null
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total": 42,
    "total_pages": 3
  },
  "error": null
}
```

---

### POST `/tasks`
Create a new task directly via API (dashboard use).

**Request**:
```json
{
  "title": "Deploy frontend",
  "description": "Deploy to production server",
  "priority": "HIGH",
  "assignee_id": "user-uuid",
  "due_date": "2026-10-10",
  "tags": ["deployment"]
}
```

**Response**: `201 Created` with task object.

---

### GET `/tasks/{task_id}`
Get single task by UUID.

**Response**: Full task object + audit log.

```json
{
  "success": true,
  "data": {
    "task": { ... },
    "audit_log": [
      {
        "action": "CREATED",
        "user": { "name": "Manager" },
        "changes": {},
        "source": "chat",
        "created_at": "2026-10-07T09:00:00Z"
      }
    ]
  }
}
```

---

### PATCH `/tasks/{task_id}`
Partially update a task.

**Request** (all fields optional):
```json
{
  "title": "Deploy frontend v2",
  "priority": "CRITICAL",
  "due_date": "2026-10-08",
  "assignee_id": "new-user-uuid"
}
```

**Response**: Updated task object.

---

### DELETE `/tasks/{task_id}`
Soft-delete a task. Requires MANAGER role.

**Response**: `204 No Content`

---

### POST `/tasks/{task_id}/complete`
Mark a task as completed.

**Request**:
```json
{ "completion_note": "Deployed successfully to prod" }
```

**Response**: Updated task object with `completed_at` set.

---

### GET `/tasks/{task_id}/history`
Get full audit history for a task.

**Response**: List of audit log entries.

---

## 4. Users API

### GET `/users`
List all users. Requires auth.

**Query Parameters**: `q` (search by name), `role`, `is_active`

**Response**: List of user objects.

---

### GET `/users/me`
Get current authenticated user.

---

### PATCH `/users/me`
Update current user preferences.

**Request**:
```json
{
  "timezone": "Asia/Kolkata",
  "daily_briefing": true,
  "briefing_time": "09:00"
}
```

---

### GET `/users/{user_id}/tasks`
Get all tasks for a specific user.

---

## 5. Analytics API

### GET `/analytics/stats`
Get aggregate task statistics.

**Query Parameters**: `user_id`, `date_from`, `date_to`

**Response**:
```json
{
  "success": true,
  "data": {
    "total_tasks": 42,
    "completed_tasks": 30,
    "overdue_tasks": 5,
    "completion_rate": 0.71,
    "avg_completion_days": 3.2,
    "tasks_by_priority": { "CRITICAL": 2, "HIGH": 10, "MEDIUM": 25, "LOW": 5 },
    "tasks_by_status": { "TODO": 5, "IN_PROGRESS": 7, "REVIEW": 0, "DONE": 30 },
    "tasks_created_per_day": [
      { "date": "2026-10-01", "count": 5 }
    ]
  }
}
```

---

### GET `/analytics/team-workload`
Get task distribution across team members.

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "user": { "id": "uuid", "name": "John Doe" },
      "total_tasks": 8,
      "overdue_tasks": 1,
      "high_priority_tasks": 3,
      "completion_rate": 0.75
    }
  ]
}
```

---

## 6. Health API

### GET `/health`
Health check endpoint. No auth required.

**Response**:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0",
  "timestamp": "2026-10-07T09:00:00Z"
}
```

---

## 7. Standard Error Responses

| Code | Meaning |
|------|---------|
| `400` | Bad Request — validation error |
| `401` | Unauthorized — missing/invalid JWT |
| `403` | Forbidden — insufficient role |
| `404` | Not Found |
| `409` | Conflict — duplicate resource |
| `422` | Unprocessable Entity — Pydantic validation |
| `429` | Too Many Requests — rate limited |
| `500` | Internal Server Error |

**Error Response Format**:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task with ID uuid-xxx was not found",
    "details": {}
  }
}
```

---

## 8. Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/chat/webhook` | 100 req/min (Google Chat rate) |
| `/tasks` (write) | 60 req/min per user |
| `/tasks` (read) | 200 req/min per user |
| `/analytics/*` | 30 req/min |
