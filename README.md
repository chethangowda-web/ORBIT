# ORBIT — Multi-Agent AI Task Management System

> Orchestrated Resource & Business Intelligence Taskmaster

A production-grade multi-agent AI system that enables employees to manage tasks through natural language in **Google Chat**, powered by **LangGraph**, **Google Gemini**, **FastAPI**, and **PostgreSQL**.

---

## ✨ Features

- 🤖 **6 Specialized AI Agents** — Supervisor, Task Manager, Planner, Recommendation, Review, Memory
- 💬 **Google Chat Integration** — Natural language task management inside your workspace
- 📋 **Full Task Management** — Create, update, assign, complete, search, filter tasks
- 🧠 **Conversation Memory** — Multi-turn context via Redis LangGraph checkpointer
- 📅 **Proactive Assistance** — Daily briefings at 9 AM, overdue alerts at 6 PM
- 🔒 **Human-in-the-Loop** — Confirmation dialogs for destructive actions
- 📊 **Next.js Dashboard** — Kanban board, filters, analytics, task detail view
- 🔍 **Observability** — LangSmith tracing + Prometheus metrics

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + FastAPI |
| Agents | LangGraph + LiteLLM |
| LLM | Google Gemini 1.5 Pro |
| Database | PostgreSQL 16 |
| Cache/State | Redis 7 |
| Scheduler | APScheduler |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Containers | Docker + Docker Compose |
| Observability | LangSmith + Prometheus |

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- Google Chat API credentials (service account)
- Google Gemini API key (or OpenAI key)

### 1. Clone & Configure
```bash
git clone https://github.com/your-username/orbit.git
cd orbit
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Services
```bash
docker-compose up -d
```

### 3. Run Migrations
```bash
docker-compose exec backend alembic upgrade head
```

### 4. Seed Database
```bash
docker-compose exec backend python -m backend.db.seed
```

### 5. Access
- **API Docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3000
- **Health Check**: http://localhost:8000/api/health

---

## 💬 Example Interactions

```
You: Create a high priority task for John to deploy the frontend by Friday
ORBIT: ✅ Task created: Deploy the frontend (Task #42)
       Priority: HIGH | Assigned to: John Doe | Due: Fri, Oct 10

You: Show my pending tasks
ORBIT: 📋 Your Pending Tasks (3):
       1. [HIGH] Deploy the frontend — Due Oct 10
       2. [MEDIUM] Review API documentation — Due Oct 12
       3. [LOW] Update team wiki — No due date

You: What should I focus on today?
ORBIT: 🎯 Today's Focus Plan:
       1. Deploy the frontend (DUE TODAY, HIGH priority)
       2. Fix authentication bug (Overdue by 2 days!)
       3. Review PR from Rahul (HIGH priority)

You: Mark the CRM deployment task as completed
ORBIT: ✅ Marked complete: CRM Deployment (Task #38)
       Completed at: 07 Oct 2026, 3:45 PM
```

---

## 🏛️ System Architecture

![ORBIT Multi-Agent System Architecture](./architecture-a2-1791376610323.png)

Detailed architecture evaluation and documentation:
- [Architecture Deep-Dive](docs/ARCHITECTURE.md)
- [Architecture & Diagram Tool Evaluation](ARCHITECTURE_EVALUATION.md)
- [Technical Design Decisions](docs/DESIGN.md)

```
Google Chat / Webhook ──► FastAPI Router ──► LangGraph Supervisor
                                                    ├── Task Agent ──► PostgreSQL
                                                    ├── Planner Agent
                                                    ├── Recommendation Agent
                                                    ├── Review Agent (HITL Guard)
                                                    └── Memory Agent ──► Redis Checkpointer
```

---

## 🔑 Default Test Credentials

All accounts seeded with password: `password123`

| Role | Email | Display Name | Permissions |
|------|-------|--------------|-------------|
| **System Admin** | `admin@orbit.dev` | System Admin | Full system administration, trigger jobs, mutate all records |
| **Manager** | `sarah@orbit.dev` | Sarah Connor | Team workload analytics, delete tasks, manual job execution |
| **Employee** | `john@orbit.dev` | John Doe | Linked to Google Chat (`users/1029384756`), task CRUD |

---

## 📁 Project Structure

```
orbit/
├── docs/
│   ├── PRD.md              # Product requirements
│   ├── ARCHITECTURE.md     # System architecture
│   ├── DESIGN.md           # Technical decisions
│   ├── AGENTS.md           # Agent contracts
│   ├── TOOLS.md            # Tool contracts
│   ├── API.md              # API contracts
│   ├── DATABASE.md         # Data model
│   ├── EVALUATION.md       # AI evaluation strategy
│   └── DECISIONS.md        # Architecture decision records
│
├── RULES.md                # Coding constraints
├── TASKS.md                # Implementation roadmap
├── MEMORY.md               # Memory strategy
│
├── backend/
│   ├── agents/             # LangGraph agents
│   ├── api/                # FastAPI routers
│   ├── crud/               # Database operations
│   ├── db/                 # Models, engine, migrations
│   ├── schemas/            # Pydantic schemas
│   ├── services/           # Google Chat service
│   ├── scheduler/          # APScheduler jobs
│   └── tools/              # Agent tools
│
├── frontend/               # Next.js dashboard
├── tests/                  # pytest test suite
├── docker-compose.yml
└── README.md
```

---

## 🔧 Environment Variables

```env
# LLM
GOOGLE_GEMINI_API_KEY=your-key
OPENAI_API_KEY=your-key (optional fallback)

# Database
DATABASE_URL=postgresql+asyncpg://orbit:password@localhost:5432/orbit

# Redis
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256

# Google Chat
GOOGLE_CHAT_WEBHOOK_SECRET=your-webhook-secret
GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service-account.json

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=orbit
```

---

## 📄 Documentation

| Document | Description |
|----------|-------------|
| [PRD.md](docs/PRD.md) | Product requirements and use cases |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full system architecture |
| [DESIGN.md](docs/DESIGN.md) | Technology choices and design decisions |
| [AGENTS.md](docs/AGENTS.md) | Agent responsibilities and contracts |
| [TOOLS.md](docs/TOOLS.md) | Tool function contracts |
| [API.md](docs/API.md) | REST API reference |
| [DATABASE.md](docs/DATABASE.md) | Database schema and models |
| [EVALUATION.md](docs/EVALUATION.md) | AI evaluation strategy |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records |
| [MEMORY.md](MEMORY.md) | State and memory strategy |
| [RULES.md](RULES.md) | Coding and architecture rules |
| [TASKS.md](TASKS.md) | Implementation roadmap |

---

## 🤝 Author

**Chethan Gowda S N**  
HiDevs Intern Assignment — Multi-Agent AI Task Management System
