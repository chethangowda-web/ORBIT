# ORBIT: Multi-Agent AI Task Management System

> Orchestrated Resource & Business Intelligence Taskmaster

Employees manage tasks in plain language inside **Google Chat**; managers get a **Mission Control** web dashboard. A LangGraph supervisor routes each request to a specialist agent, every change is audited, and proactive briefings keep people on track.

---

## Features

- **Six cooperating agents**: Supervisor, Task, Planner, Recommendation, Review (human-in-the-loop) and Memory, orchestrated with LangGraph.
- **Google Chat bot**: natural-language task management, interactive confirmation cards, direct-message notifications, idempotent webhook handling.
- **Mission Control dashboard** (Next.js 14): drag-and-drop board, dense task table with URL-synced filters, task detail with a readable audit trail, insights charts, agent run traces, admin console, command palette (`Ctrl+K`) and an always-available agent panel.
- **Collaboration**: comments on tasks (assignee and creator notified in Chat), bulk actions on the task table (complete, status, priority, assign, delete) with per-task permission checks.
- **Live dashboard**: changes made anywhere (another browser, Google Chat, the scheduler) appear instantly via Server-Sent Events, with polling as a fallback.
- **Attachments**: files on tasks (documents, images, spreadsheets, zip), validated by type and size, always downloaded as attachments.
- **Email notifications** (optional): the same assignment, update and comment notices as Chat, per-user opt-out, enabled by setting SMTP variables.
- **Light, dark and system themes**, remembered per browser and rendered without a flash.
- **Role-based access** (employee, manager, admin) enforced identically in the REST API *and* in the chat agents' tools.
- **Proactive assistance**: 9:00 morning briefing, 18:00 overdue alerts, Monday weekly summary; per-user opt-outs honoured; honest delivery logging (`sent`, `failed`, `skipped`).
- **Conversation memory**: Redis-backed LangGraph checkpoints, so "make it high priority" resolves across turns.
- **Offline-safe**: with no LLM key configured, a deterministic classifier keeps the whole system working.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2 (async), Alembic |
| Agents | LangGraph, LiteLLM (Gemini by default, OpenAI fallback) |
| Data | PostgreSQL 16, Redis 7 |
| Scheduler | APScheduler (Redis job store, Redis job locks) |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, TanStack Query, Recharts, dnd-kit |
| Tests | pytest (backend), Vitest + Testing Library (frontend), Playwright (end to end) |

---

## Quick start (local development)

Prerequisites: Python 3.11+, Node 20+, Docker (for Postgres and Redis).

```bash
git clone <your-fork-url> orbit && cd orbit
cp .env.example .env              # defaults work for local development

docker compose up -d postgres redis

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m db.seed                                       # demo users and tasks (development only)
uvicorn main:app --port 8001

# Frontend (new terminal)
cd frontend
npm ci
npm run dev                                             # http://localhost:3000
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API docs (Swagger) | http://localhost:8001/docs |
| Health | http://localhost:8001/api/health |

### Everything in Docker

```bash
cp .env.example .env     # set JWT_SECRET_KEY; SEED_ON_START=true for demo data
docker compose up -d --build
```

If pulling `python`/`node` times out (Docker Hub unreachable), build through a mirror: set `PYTHON_IMAGE=mirror.gcr.io/library/python:3.11-slim` and `NODE_IMAGE=mirror.gcr.io/library/node:20-alpine` in `.env`. If port 6379 is taken by another project, set `REDIS_PORT=6380`.

The backend container applies migrations on start (and seeds when `SEED_ON_START=true`). The frontend image bakes in `NEXT_PUBLIC_API_URL` at **build** time, so rebuild it if the API URL changes.

### Demo accounts (development only)

`python -m db.seed` creates these with the password `password123`. Production refuses to seed unless `SEED_PASSWORD` is set.

| Role | Email | Can |
|---|---|---|
| Admin | `admin@orbit.dev` | everything, including users and roles |
| Manager | `sarah@orbit.dev` | team tasks, delete, insights, scheduler, notification log |
| Employee | `john@orbit.dev` | own tasks (assigned or created), own stats |

---

## Using ORBIT

### In Google Chat

```
You:   Create a high priority task for John to deploy the frontend by Friday
ORBIT: Created Task: Deploy the frontend  (HIGH, due Fri)

You:   Show my pending tasks
You:   What should I focus on today?
You:   Make it critical            <- "it" resolves from the previous turn
You:   Delete the old login task   <- managers get a Confirm / Cancel card
```

ORBIT never guesses: an unknown or ambiguous name ("Joe" matches two people) or an unclear task ("complete it" with no context) produces a clarifying question instead of an action.

### In the dashboard

- **Board**: drag cards between lanes (or use the arrow on a card). `Mine` / `Everyone` scope toggle.
- **Tasks**: search title, description and tags; filter by status, priority, assignee, overdue; sort columns. Filters live in the URL so views are shareable. Tick rows (or the header box) for bulk actions.
- **Task page**: fields, a comment thread (`Ctrl+Enter` to send) and a readable activity log.
- **Agent panel** (top bar, or `Ctrl+K` then type a request): chat with the agents, confirm destructive actions, inspect which agents ran and how long each took.
- **Insights** (managers): completion, status and priority mix, creation trend, workload per person, all computed from the database.
- **Agent runs**: every request's route, tools and timings.
- **Admin** (managers; users tab for admins): scheduler status and manual triggers, notification delivery log, user roles and activation.

---

## Google Chat setup

Full walkthrough with a verification checklist: [docs/GOOGLE_CHAT_SETUP.md](docs/GOOGLE_CHAT_SETUP.md). Try the bot first without Google: `cd backend && python -m scripts.simulate_chat --email john@orbit.dev`.

Slash commands: `/tasks`, `/plan`, `/overdue`, `/insights`, `/help`, `/new <title>`. Task lists come back as cards with a **Done** button per task.

1. In Google Cloud, enable the **Google Chat API** and create a service account with the Chat Bot role. Save its key as `credentials/service-account.json` (never commit it).
2. Configure the Chat app: HTTP endpoint, **Receive 1:1 messages**, **Join spaces**.
3. Expose your backend over HTTPS (for local work: `ngrok http 8001`) and set the endpoint URL to `https://<host>/api/chat/webhook`.
4. Choose an **Authentication audience** in the Chat app configuration and mirror it in `.env`:
   - *Project number*: `GOOGLE_CHAT_AUDIENCE=<project number>`
   - *HTTP endpoint URL*: `GOOGLE_CHAT_AUDIENCE=https://<host>/api/chat/webhook`
5. **Production**: set `GOOGLE_CHAT_VERIFY_AUTH=true`. ORBIT then accepts only Google-signed requests from the Chat service account; the app refuses to start in production with verification off or no audience.

Proactive direct messages work by finding the bot's DM space with each user, or by using the DM space remembered from their first message. Users with no linked Google Chat account at all are logged as `skipped`; if the DM lookup or delivery fails the log says `failed` with the reason (see Admin, Notifications).

---

## Testing

```bash
# Backend: fully offline (no LLM or Google calls), ~1 minute
pytest

# Frontend unit and component tests
cd frontend && npm test && npm run typecheck && npm run lint

# End to end (needs the running stack with seeded data)
cd frontend && npm run build && npm start      # in one terminal
cd frontend && npm run test:e2e                # in another
```

Set `ORBIT_LIVE_LLM=1` to let backend tests call a real model (manual evaluation only). `E2E_SCREENSHOTS=1 npx playwright test e2e/screens.spec.ts` captures every screen to `frontend/test-results/screens/`.

---

## Configuration

All settings are environment variables; see [`.env.example`](.env.example) for the full annotated list. The ones that matter most:

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `production` turns on safety checks (strong JWT secret, no wildcard CORS, Chat verification on) and the app refuses to boot otherwise |
| `JWT_SECRET_KEY` | Required in production, 32+ random characters |
| `GOOGLE_GEMINI_API_KEY` / `OPENAI_API_KEY` | Leave empty to run on the offline classifier |
| `APP_TIMEZONE` | Defines "today" for due dates, digests and the scheduler (default `Asia/Kolkata`) |
| `ALLOW_REGISTRATION` | Public sign-up, off by default |
| `GOOGLE_CHAT_VERIFY_AUTH`, `GOOGLE_CHAT_AUDIENCE`, `GOOGLE_CHAT_WEBHOOK_SECRET` | Webhook authentication |
| `SCHEDULER_ENABLED`, `SCHEDULER_JOBSTORE` | Scheduler on/off, `redis` or `memory` |

---

## Project layout

```
backend/
  agents/       LangGraph supervisor, specialists, memory, orchestrator, prompts
  api/          FastAPI routers (auth, tasks, users, analytics, admin, chat webhook)
  auth/         JWT, Google OAuth, RBAC rules, login rate limiter
  crud/         Database operations
  db/           Models, session, seed
  alembic/      Migrations (run with: alembic upgrade head)
  schemas/      Pydantic request and response models
  scheduler/    Cron jobs (briefing, overdue alerts, weekly summary)
  services/     LLM client, Google Chat client, notification dispatcher
  tools/        Agent tools (permission-checked, never raise)
frontend/
  app/          Routes: (auth) login and OAuth callback, (app) board, tasks, insights, traces, admin, profile
  components/   ui/ (design-system kit), shell/, tasks/, agent/
  lib/          API client, auth, hooks, formatting and query helpers
  __tests__/    Vitest unit and component tests
  e2e/          Playwright end-to-end tests
tests/          pytest suite (API, agents, RBAC, webhook, scheduler, migrations)
docs/           Architecture, API, data model, design system, decisions
```

---

## Documentation

| Document | Contents |
|---|---|
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Deployment, security checklist, runbook, troubleshooting |
| [docs/GOOGLE_CHAT_SETUP.md](docs/GOOGLE_CHAT_SETUP.md) | Step-by-step Google Chat setup, slash commands, local simulator, checklist |
| [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) | Deploy the API and Chat webhook to Render (`render.yaml`) with a fixed HTTPS address |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and request flows |
| [docs/AGENTS.md](docs/AGENTS.md) | Agent responsibilities, routing, safety rules |
| [docs/TOOLS.md](docs/TOOLS.md) | Tool contracts and permission model |
| [docs/API.md](docs/API.md) | REST API reference |
| [docs/DATABASE.md](docs/DATABASE.md) | Schema and migrations |
| [docs/DESIGN_MISSION_CONTROL.md](docs/DESIGN_MISSION_CONTROL.md) | Dashboard design system |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision records |
| [docs/EVALUATION.md](docs/EVALUATION.md) | How agent quality is measured |
| [docs/PRD.md](docs/PRD.md), [docs/DESIGN.md](docs/DESIGN.md) | Original product requirements and technology choices |
| [RULES.md](RULES.md), [TASKS.md](TASKS.md), [MEMORY.md](MEMORY.md) | Engineering rules, roadmap, memory strategy |

## Author

**Chethan Gowda S N**: HiDevs Intern Assignment, Multi-Agent AI Task Management System.
