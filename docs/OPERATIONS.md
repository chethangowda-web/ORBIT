# OPERATIONS.md: Deploy, Secure, Run, Troubleshoot

Everything an operator needs to run ORBIT. For design background see ARCHITECTURE.md.

---

## 1. Production checklist

ORBIT refuses to start with `ENVIRONMENT=production` unless these hold (`backend/config.py`):

| Requirement | Why |
|---|---|
| `JWT_SECRET_KEY` is unique, 32+ chars, not a placeholder | Anyone who knows it can mint tokens for any user, including admins |
| `CORS_ORIGINS` has no `*` | Credentials are allowed cross-origin |
| `GOOGLE_CHAT_VERIFY_AUTH=true` | Otherwise anyone can post forged chat events as any user |
| `GOOGLE_CHAT_AUDIENCE` set | Without an audience every token would pass; ORBIT rejects all instead |

Also do:

- [ ] Use a managed Postgres with backups and a managed or persistent Redis.
- [ ] Put the API and dashboard behind HTTPS (the OAuth cookie is `Secure` when `ENVIRONMENT=production`).
- [ ] Set `ALLOW_REGISTRATION=false` (the default) and provision users through Google sign-in or the Admin screen.
- [ ] Seed with `SEED_PASSWORD` (12+ chars) or do not seed; never ship `password123`.
- [ ] Keep `credentials/` and `.env` out of images and version control (the `.dockerignore` files exclude them).
- [ ] Rotate any service-account key that has ever been committed to a repository.
- [ ] Leave `LOG_WEBHOOK_PAYLOADS=false` (payloads contain names, emails and message text).
- [ ] Run more than one API worker only with Redis available: the login limiter and scheduler locks need it to be shared.

## 2. Deploying

### Docker Compose

```bash
cp .env.example .env            # fill in secrets, set ENVIRONMENT=production for real deployments
docker compose up -d --build
docker compose ps               # all four services should become healthy
```

- The **backend** entrypoint runs `alembic upgrade head` before starting, so schema changes ship with the image. `SEED_ON_START=true` also runs the seed once (safe to repeat: it does nothing if users exist).
- The **frontend** image inlines `NEXT_PUBLIC_API_URL` at build time. Pass it as a build arg (compose does) and rebuild when the public API URL changes.
- Compose publishes the backend on host port `${PORT:-8001}` and the dashboard on `3000`.

### Migrations

```bash
cd backend
alembic upgrade head            # apply
alembic downgrade -1            # roll back one step
alembic check                   # fails if models and migrations disagree (CI runs this)
alembic revision --autogenerate -m "describe change"   # then review the file before committing
```

Migration 004 is index-only (renames and removes redundant indexes) and is safe to apply online.

## 3. Roles and access

| Capability | Employee | Manager | Admin |
|---|:-:|:-:|:-:|
| See / edit / complete tasks they created or are assigned | yes | yes | yes |
| See and edit every task | | yes | yes |
| Assign tasks to other people | | yes | yes |
| Delete tasks | | yes | yes |
| Team insights, scheduler, notification log | | yes | yes |
| Change roles, deactivate users | | | yes |

The same rules apply in chat: the agent tools take the caller's identity and apply the same checks, so asking ORBIT cannot reveal or change what the dashboard would refuse. Safeguards: admins cannot demote or deactivate themselves, and the last active admin cannot be removed.

## 4. Scheduled jobs

| Job | Time (`APP_TIMEZONE`) | Opt-out preference |
|---|---|---|
| Morning briefing | 09:00 daily | `daily_briefing` |
| Overdue alerts | 18:00 daily | `overdue_alert` |
| Weekly summary (managers, admins) | Monday 09:30 | `weekly_summary` |

- Each user toggles these on the Profile page (stored as `user_preferences`).
- A Redis lock (`orbit:lock:scheduler:<job>`, 5 minute TTL) stops several workers from running the same firing; if Redis is down the job still runs and the per-day dedupe in `notification_logs` limits duplicates.
- Manual runs (Admin, Scheduler) bypass the once-per-day dedupe but still honour opt-outs, and ask for confirmation first because they send real messages.

## 5. Observability

- **Agent runs**: every request records route, tools, per-agent timings and status (`agent_execution_traces`); the dashboard shows them under *Agent runs*.
- **Notification log**: Admin, Notifications shows each delivery with its true outcome. `skipped` = no Google Chat account linked; `failed` = delivery attempted and failed (reason shown).
- **Logs**: structured to stdout at `LOG_LEVEL`. Unhandled errors log a stack trace and return a short reference id (`ref abc123def456`) to the user; search the logs for that id.
- **Health**: `GET /api/health` (public) reports `database`, `redis` and checkpointer mode without exposing connection details. `GET /health` is the liveness probe used by Docker.
- **Metrics**: set `METRICS_ENABLED=true` (and `METRICS_TOKEN` to require `Authorization: Bearer <token>`) to expose Prometheus metrics at `/metrics`:

  | Metric | Labels |
  |---|---|
  | `orbit_http_requests_total`, `orbit_http_request_duration_seconds` | method, route template, status |
  | `orbit_agent_runs_total`, `orbit_agent_run_duration_seconds` | intent, status |
  | `orbit_tool_calls_total` | tool |
  | `orbit_notifications_total` | type, status (`sent`, `failed`, `skipped`) |

  Labels are low-cardinality by design (route templates, never raw URLs or ids). Metrics are per process; scrape every worker. A useful alert: `rate(orbit_notifications_total{status="failed"}[15m]) > 0`.
- Optional LangSmith tracing: set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY`.

## 6. Testing and CI

```bash
pytest                                   # backend, offline, ~1 min
cd frontend && npm test                  # unit and component
cd frontend && npm run typecheck && npm run lint && npm run build
cd frontend && npm run test:e2e          # needs the running stack
```

The backend tests never contact an LLM or Google (`tests/conftest.py` blanks the keys). `.github/workflows/ci.yml` runs the backend suite, migration drift check, frontend checks and build on every push and pull request.

## 7. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Backend exits with `Unsafe production configuration` | One of the section 1 requirements is missing; the message names which |
| Dashboard shows "API unreachable" | Browser cannot reach `NEXT_PUBLIC_API_URL` (baked at build time) or CORS_ORIGINS lacks the dashboard origin |
| Google sign-in button says not configured | `GOOGLE_OAUTH_CLIENT_ID` is empty; the redirect URI must equal `GOOGLE_OAUTH_REDIRECT_URI` exactly |
| Chat messages get 401 | `GOOGLE_CHAT_VERIFY_AUTH=true` but the audience does not match the Chat app's *Authentication audience*, or the request did not come from Google |
| Chat messages get 403 | `GOOGLE_CHAT_WEBHOOK_SECRET` is set but the request lacks a valid `X-Goog-Signature` |
| Briefings logged `skipped` | The user has no linked Google Chat account; have them message the bot once |
| Briefings logged `failed` | Read the reason in the Notification log; usually the service account is not allowed in that space or DM lookup failed |
| 429 on sign-in | Too many failed attempts for that IP and email; wait `LOGIN_RATE_LIMIT_WINDOW_SECONDS` |
| Replies are generic or slow | LLM key empty (offline classifier) or the provider is failing; ORBIT retries three times with backoff, then falls back |
| `alembic check` reports drift | A model changed without a migration; generate one and review it |
| Docker build fails with `TLS handshake timeout` pulling `python` or `node` | Docker Hub is unreachable from your network. Build through a mirror: `PYTHON_IMAGE=mirror.gcr.io/library/python:3.11-slim NODE_IMAGE=mirror.gcr.io/library/node:20-alpine docker compose up -d --build` (Linux/macOS), or set those two variables in `.env`. The same two variables work as `--build-arg`s |
| `Bind for 0.0.0.0:6379 failed: port is already allocated` | Another project uses Redis's host port. Set `REDIS_PORT=6380` in `.env` (containers talk to each other over the internal network, unaffected) |

## 7a. Optional features

**Email notifications.** Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY` (`starttls`, `ssl` or `none`) and `EMAIL_FROM`; set `APP_BASE_URL` so links in emails point at the dashboard. Email is sent next to the Google Chat message for assignments, updates, completions and comments, and each delivery is logged in `notification_logs` (`email:<type>`; `sent`, `failed` or `skipped`). Users opt out with the "Email notifications" switch on their profile. A mail outage never affects the task change: the send is bounded by `SMTP_TIMEOUT` and failures are only logged.

**Attachments.** Files are stored in `UPLOAD_DIR` (`/app/uploads`, the `uploads_data` volume, in Compose). Limits: `MAX_UPLOAD_MB` (10) and `MAX_ATTACHMENTS_PER_TASK` (20). Back the volume up with the database. If you put a reverse proxy in front, raise its body-size limit to at least `MAX_UPLOAD_MB` (nginx: `client_max_body_size`).

**Live updates (SSE).** `GET /api/events/stream`. The hub is in-process, so it is exact with one API process. With several workers a change reaches only the dashboards connected to the worker that handled it; the dashboard still polls every 15 seconds, so it converges, and a Redis pub/sub bus is the upgrade path. If a proxy sits in front, disable response buffering for this path (the API already sends `X-Accel-Buffering: no`) and allow connections that stay open for hours.

**Themes.** Dark (default), light, or follow the system; stored in the `orbit_theme` cookie and applied on the server so there is no flash.

## 7b. Staying up when dependencies fail

| Failure | What happens |
|---|---|
| LLM provider slow | Each attempt is cut off after `LLM_TIMEOUT_SECONDS` (8) |
| LLM provider failing or out of quota | After `LLM_BREAKER_FAILURES` (3) consecutive failures the LLM is skipped for `LLM_BREAKER_COOLDOWN_SECONDS` (60); the offline classifier answers instantly, then one request probes the provider again |
| Agent pipeline stuck | Replies "timed out, please try again" after `AGENT_TIMEOUT_SECONDS` (22), inside Google Chat's 30 second limit |
| Unexpected error while handling a Chat event | HTTP 200 with a short apology and an error reference found in the logs |
| Redis down | Conversation memory falls back to process memory outside production; the login limiter uses an in-process counter; the dashboard shows "Cache offline" |
| SMTP or Google Chat delivery failing | Retried briefly, logged as `failed`; the task change is never rolled back |
| Database connection dropped | Pool pre-ping replaces dead connections |
| Container crash | `restart: unless-stopped` plus health checks; migrations re-run safely on start |

**Keeping a Windows dev machine reachable.** The bot answers only while Docker Desktop and the ORBIT containers are running. Docker Desktop does not always start after a reboot, which shows up in Google Chat as "not responding" (ngrok then reports 502 for `localhost:8001`). `backend/scripts/keep_orbit_running.ps1` starts Docker Desktop if needed and brings up postgres, redis and the backend; it does nothing when all is well. Register it once (no admin rights needed):

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"D:/ORBIT/backend/scripts/keep_orbit_running.ps1`""
$logon  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$every5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "ORBIT keep running" -Action $action -Trigger @($logon,$every5) -Force
```

Remove it with `Unregister-ScheduledTask -TaskName "ORBIT keep running" -Confirm:$false`. Its log is `%LOCALAPPDATA%/orbit-autostart.log`. It cannot help while the PC is asleep or off; for an always-on bot, deploy the backend to a host.

## 8. Known limitations

- Uploaded files are not virus-scanned; the type allow-list and attachment-only downloads limit the risk but do not remove it. Add a scanner (for example ClamAV) before accepting files from untrusted users.
- Files of a soft-deleted task stay on disk with the task row.

- Conversation state lives in Redis with a 24 hour TTL; a Redis flush ends open conversations (pending delete confirmations are lost safely: nothing is deleted without a fresh confirmation).
- Task search is substring-based (`LIKE`), fine for thousands of tasks; add a Postgres full-text index if the table grows into the hundreds of thousands.
- The dashboard sends a per-request, nonce-based Content-Security-Policy (`frontend/middleware.ts`, `frontend/lib/csp.ts`): scripts run only if same-origin or carrying the request's nonce, `connect-src` is limited to the app and the API origin, and framing is denied. Every page is therefore rendered per request rather than prerendered. Browser tests assert zero violations on every screen and that injected inline handlers do not run. If you add a third-party script or API origin, extend the policy there.
- The dashboard keeps the bearer token in `localStorage` (the API is cross-origin and authenticates with an `Authorization` header), so a cross-site-scripting bug would expose it. Mitigations in place: agent text is rendered as React nodes, never HTML; security headers (`X-Frame-Options: DENY`, `nosniff`, referrer and permissions policies) are sent; there is no `dangerouslySetInnerHTML`. Moving to an HttpOnly cookie session is a recommended next step if the dashboard and API share a site.
- Tokens are valid until expiry (default 24 hours); there is no server-side revocation list, so deactivating a user takes effect immediately (the user row is checked on every request) but a stolen token for an *active* user stays valid until it expires.
