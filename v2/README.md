# ORBIT v2

Ground-up rebuild of ORBIT. Built beside the current app (`backend/`, `frontend/`)
so nothing is removed until v2 reaches parity. Branch: `feature/v2-rebuild`.

## Decisions
- Same stack: FastAPI, LangGraph, LiteLLM (Gemini), PostgreSQL 16, Redis 7,
  APScheduler, Next.js 14 App Router.
- Same API envelope: `{success, data, meta, error}`.
- New dashboard design: Mission Control (see `docs/DESIGN_MISSION_CONTROL.md`).
- v2 runs on separate ports so it can run next to v1:
  Postgres 5433, Redis 6380, backend 8002, frontend 3001.

## Layout
```
v2/
  docs/        specs (design now; API, agents, data model as they are written)
  backend/     FastAPI app, agents, migrations, tests
  frontend/    Next.js app
  docker-compose.yml
  .env.example
```

## Phases
1. Foundation (this commit): layout, design spec, compose, env.
2. Backend core: config, DB, migrations, auth and roles, task/user/analytics APIs.
3. Agent layer: supervisor, specialists, confirmation flow, traces.
4. Integrations: Google Chat webhook, idempotency, scheduler, notifications.
5. Frontend: UI kit, shell, pages.
6. Verification: tests, intent eval, browser pass, full Docker run.

## Run infrastructure
```bash
cd v2
cp .env.example .env
docker compose up -d postgres redis
```
