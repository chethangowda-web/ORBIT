# API.md: REST API Reference

**Base URL (local):** `http://localhost:8001/api`  ·  **Interactive docs:** `/docs`
**Auth:** `Authorization: Bearer <JWT>` on everything except `/health`, `/auth/token`, the Google OAuth start/callback/link routes, and the Chat webhook (which has its own verification).

## Envelope

Every response, success or error, uses one shape:

```json
{ "success": true, "data": { }, "meta": null, "error": null }
```

Lists put pagination in `meta`: `{ "page": 1, "page_size": 20, "total": 42, "total_pages": 3 }`.
Errors set `success: false`, `data: null` and a human-readable `error` string. Some errors carry machine-readable `meta` (for example the Google account-link case below).

| Status | Meaning |
|---|---|
| 400 | Bad request (invalid event schema, etc.) |
| 401 | Missing, invalid or expired token; or invalid Chat webhook authentication |
| 403 | Authenticated but not allowed (role or object-level rule, registration disabled, bad webhook signature) |
| 404 | Not found, or not visible to you (tasks you cannot see return 404, not 403, so existence is not disclosed through chat) |
| 409 | Conflict (duplicate account, Google account needs linking, last-admin and self-lockout protections, cancelled task completion) |
| 422 | Validation error (field-level message in `error`) |
| 429 | Too many failed sign-in attempts |
| 500 | Unexpected error; the message includes a reference id that is also in the server log |

## Roles

`employee` sees and edits only tasks they created or are assigned. `manager` and `admin` see everything; only they may delete tasks, assign to others, and read team analytics, the scheduler and the notification log. Only `admin` manages users. See OPERATIONS.md section 3.

---

## Authentication

### `POST /auth/token`
Body `{ "email", "password" }`. Returns `{ access_token, token_type: "bearer", expires_in, user: { id, email, display_name, role, google_space_id } }`.
Failed attempts are counted per client IP + email; after `LOGIN_RATE_LIMIT_ATTEMPTS` (default 10) in the window the response is **429** until it passes. A successful login clears the counter. Email matching is case-insensitive.

### `POST /auth/register`
Returns **403** unless `ALLOW_REGISTRATION=true`. When enabled: body `{ email, password (10 to 128 chars), display_name, timezone? }`; the new account is always an `employee` regardless of any role sent.

### Google sign-in
- `GET /auth/google/url` returns `{ authorization_url, state }` and sets a short-lived HttpOnly state cookie (PKCE + nonce). 503 if Google OAuth is not configured.
- `POST /auth/google/callback` body `{ code, state }` verifies state, the ID token and nonce, then returns the same payload as `/auth/token`. New Google users are created as `employee`.
- If the email already belongs to a password account the response is **409** with `meta: { code: "ACCOUNT_LINK_REQUIRED", link_token, email }`.
- `POST /auth/google/link` body `{ link_token, password }` verifies the existing password, links the Google identity and returns a token.

### `POST /auth/logout`, `GET /auth/me`
Logout clears the OAuth state cookie (tokens are stateless; the client discards its token). `/auth/me` returns the session summary; use `/users/me` for the full profile.

---

## Tasks

### `GET /tasks`
| Param | Type | Notes |
|---|---|---|
| `status`, `priority` | repeatable | `status=TODO&status=REVIEW` |
| `assignee_id`, `created_by_id` | UUID | Ignored for employees (they are always scoped to their own tasks) |
| `due_before`, `due_after` | date | Inclusive |
| `q` | string | Case-insensitive substring over title, description and tags; `%` and `_` are literal |
| `include_completed` | bool, default `true` | Ignored when `status` is given |
| `page`, `page_size` | int | `page_size` 1 to 100, default 20 |
| `sort_by` | `due_date` (default), `created_at`, `updated_at`, `priority`, `status`, `title` | Unknown values fall back to `due_date` |
| `sort_dir` | `asc` / `desc` | |

Each task: `id, title, description, status, priority, assignee_id, created_by_id, due_date, completed_at, tags, created_at, updated_at, days_overdue, assignee, creator` where `assignee` and `creator` are the directory view (`id, email, display_name, role, avatar_url, is_active`).

### `POST /tasks` (201)
Body `{ title (1 to 255), description?, priority (LOW|MEDIUM|HIGH|CRITICAL), assignee_id?, due_date?, tags? }`. Employees may only assign to themselves (403 otherwise). Notifies the assignee in Google Chat when they are not the creator.

### `GET /tasks/overdue`, `GET /tasks/{id}`
Overdue = due date before today in `APP_TIMEZONE`, status not DONE or CANCELLED. Detail includes `audit_logs`.

### `PATCH /tasks/{id}`
Any of `title, description, status, priority, assignee_id, due_date, tags`. Moving to `DONE` stamps `completed_at`; moving a DONE task back clears it. Reassignment follows the same employee restriction as creation.

### `POST /tasks/{id}/complete`
Body `{ completion_note? }`. Idempotent (completing a DONE task returns it unchanged and records nothing new). A CANCELLED task returns **409**. Notifies the creator.

### `DELETE /tasks/{id}` (manager, admin)
Soft delete. Recorded in the audit log.

### `POST /tasks/bulk`
Apply one action to up to 50 tasks. Body `{ task_ids: [uuid], action, value? }` where `action` is one of:

| action | `value` | Rule |
|---|---|---|
| `complete` | none | Same as `POST /tasks/{id}/complete` per task |
| `set_status` | a status | Same as `PATCH` |
| `set_priority` | a priority | Same as `PATCH` |
| `assign` | user id, or empty to unassign | Employees may only assign to themselves |
| `delete` | none | Managers and admins only |

Every task is authorised individually and one failure never stops the rest. Response (always 200 for a valid request): `{ succeeded: [ids], failed: [{ id, reason }] }`. Duplicate ids are processed once; unknown ids, cancelled tasks being completed, and forbidden tasks appear in `failed` with the reason.

### Comments
- `GET /tasks/{id}/comments`: oldest first, with `author` (directory view). Requires permission to view the task.
- `POST /tasks/{id}/comments` (201): body `{ body }` (1 to 2000 characters, trimmed, blank rejected). Adds a `COMMENTED` entry to the task history and notifies the assignee and creator in Google Chat (never the author).
- `DELETE /tasks/{id}/comments/{comment_id}`: the author, or any manager or admin. A comment id that belongs to a different task returns 404.

### `GET /tasks/{id}/history`
Audit entries, newest first: `{ id, action, changes: { field: { old, new } }, source: "api" | "chat" | "scheduler", created_at, user }`.

---

## Users

| Endpoint | Who | Notes |
|---|---|---|
| `GET /users` | any | `q, role, is_active, page, page_size`. Directory view; employees never see deactivated users |
| `GET /users/me` | any | Full profile including `timezone`, `google_id`, `google_space_id` |
| `PATCH /users/me` | any | `display_name, first_name, last_name, timezone` only (validated IANA zone). Role, active flag and chat identifiers cannot be self-edited |
| `GET /users/me/preferences`, `PATCH /users/me/preferences` | any | Body `{ preferences: { "daily_briefing": "false" } }`. Keys: `daily_briefing`, `overdue_alert`, `weekly_summary`. `false`/`0`/`off`/`no` opts out |
| `GET /users/{id}` | any | Directory view; managers and admins get the full record |
| `PATCH /users/{id}` | admin | `{ role?, is_active? }`. 409 if you would demote or deactivate yourself, or remove the last active admin. `PATCH /users/{id}/role` is a deprecated alias |
| `GET /users/{id}/tasks` | any | Employees may only query themselves |

---

## Analytics

### `GET /analytics/stats`
Computed with SQL aggregates over non-deleted tasks. Employees get their own scope (assigned or created, matching the task list); managers and admins get everything, or one person with `user_id`. Optional `date_from`, `date_to` filter by creation date.

```json
{
  "total_tasks": 14, "completed_tasks": 8, "in_progress_tasks": 2, "overdue_tasks": 1,
  "completion_rate": 0.57,
  "avg_completion_days": 0.5,
  "by_status":   { "TODO": 3, "IN_PROGRESS": 2, "REVIEW": 1, "DONE": 8, "CANCELLED": 0 },
  "by_priority": { "CRITICAL": 3, "HIGH": 6, "MEDIUM": 3, "LOW": 2 },
  "tasks_created_per_day": [ { "date": "2026-10-10", "count": 4 } ]
}
```
`avg_completion_days` is the mean of `completed_at - created_at` over completed tasks (0 when there are none). `tasks_created_per_day` covers the last 14 days with zero-filled gaps. `tasks_by_status` and `tasks_by_priority` repeat the two maps for older clients.

### `GET /analytics/team-workload` (manager, admin)
Per active user: `user_id, display_name, email, role, assigned_tasks, completed_tasks, overdue_tasks, high_priority_tasks, completion_rate`, from a single grouped query.

---

## Admin (manager, admin)

| Endpoint | Purpose |
|---|---|
| `GET /admin/scheduler/status` | `{ running, job_count, jobs: [{ id, name, next_run_time, trigger }], timezone }` |
| `POST /admin/trigger-briefing`, `/trigger-overdue-alerts`, `/trigger-weekly-summary` | Run a job now. `?force=true` (default) bypasses the once-per-day dedupe; opt-outs are always honoured. Returns counts such as `{ processed, sent, skipped, failed }` |
| `GET /admin/notifications` | Delivery log, newest first. Filters `status` (`sent`/`failed`/`skipped`), `type`, `page`, `page_size`. Each entry has the recipient name, outcome and error |

---

## Chat

### `POST /chat/webhook`
Google Chat HTTP endpoint (also served at `/webhook` and `/api/cha` for older configurations; these aliases are hidden from the schema).

Authentication:
- `GOOGLE_CHAT_VERIFY_AUTH=true`: the `Authorization: Bearer` token must be Google-signed for the configured audience and issued to `chat@system.gserviceaccount.com` (OIDC email claim, or the Chat service account's own signed JWT). A valid `X-Goog-Signature` HMAC is accepted as an alternative when `GOOGLE_CHAT_WEBHOOK_SECRET` is set.
- Verification off (development): if `GOOGLE_CHAT_WEBHOOK_SECRET` is set, a valid `X-Goog-Signature` (HMAC-SHA256 of the raw body) is **mandatory**; omitting the header is rejected with 403.

Events: `MESSAGE`, `CARD_CLICKED` (Confirm, Cancel, Complete), `ADDED_TO_SPACE`, `APP_HOME`. `MESSAGE` and `CARD_CLICKED` are idempotent: a redelivered event returns the first response and never re-runs tools. Unknown card actions are ignored. Errors reach the user only as a generic message with a reference id.

### `POST /chat/query`
Dashboard agent endpoint. Body `{ message (1 to 2000 chars), thread_id? (<=100), confirmed? }`. Threads are namespaced per user, so one user can never read or continue another's conversation. Returns `{ response, thread_id, message_id, needs_confirmation, referenced_task_id, referenced_tasks, suggested_actions, metadata: { request_id, active_agent, agents_invoked, intent, confidence, tool_calls_made, node_durations_ms, total_duration_ms, status } }`.

### `GET /chat/traces?limit&offset`, `GET /chat/traces/{id}`
Your own agent runs only (another user's trace id returns 404).

---

## Health

- `GET /api/health` (public): `{ status, database: "connected" | "disconnected", redis, checkpoint: { backend, is_durable, connected, mode } }`. Never includes connection strings or exception text.
- `GET /health`: liveness probe, always `{ "status": "healthy" }` when the process is up.

## Rate limiting

Only sign-in is rate limited (see `POST /auth/token`). Other endpoints are not throttled by ORBIT; apply limits at your reverse proxy or gateway if you expose the API publicly.
