# PRD.md — Product Requirements Document
# ORBIT: Multi-Agent AI Task Management System

**Version:** 1.0.0  
**Author:** Chethan Gowda S N  
**Status:** Active  
**Last Updated:** 2026-10-07  

---

## 1. Overview

### 1.1 Product Name
**ORBIT** — Orchestrated Resource & Business Intelligence Taskmaster

### 1.2 One-Liner
ORBIT is a multi-agent AI system that lets employees manage tasks through natural language in Google Chat, backed by an intelligent orchestration layer that plans, validates, schedules, and proactively assists users.

### 1.3 Problem Statement
In modern organizations, task management and team communication live in separate tools. Employees switch context between chat platforms and project managers, losing productivity. There is no system that:
- Understands natural language task requests inside a chat platform
- Proactively reminds, prioritizes, and summarizes work
- Provides intelligent recommendations based on workload and deadlines
- Gives managers a real-time dashboard of team task health

### 1.4 Solution
An AI-powered task management system that:
1. Lives natively inside **Google Chat** as a bot
2. Accepts natural language commands and converts them into structured task operations
3. Uses a **multi-agent architecture** (LangGraph) to orchestrate specialized agents
4. Proactively sends reminders, daily briefings, and overdue alerts
5. Exposes a **Next.js dashboard** for visual task management

---

## 2. Target Users

| Persona | Role | Key Needs |
|---------|------|-----------|
| **Employee** | Individual contributor | Quick task creation, see my tasks, get reminders |
| **Manager** | Team lead | Assign tasks to others, see team status, productivity summary |
| **Admin** | System admin | User management, system health, audit logs |

---

## 3. Core Use Cases

### UC-01: Natural Language Task Creation
> "Create a high priority task for John to deploy the frontend by Friday."
- Extracts: assignee, priority, title, due date
- Confirms back in Google Chat with task ID

### UC-02: Task Assignment
> "Assign API testing to Rahul."
- Identifies/creates task, assigns to Rahul, notifies Rahul

### UC-03: View My Tasks
> "Show my pending tasks."
- Returns formatted list of open/in-progress tasks sorted by priority

### UC-04: Daily Planning Assistance
> "What should I focus on today?"
- Planner Agent returns top 3–5 prioritized tasks with reasoning

### UC-05: Mark Task Complete
> "Mark the CRM deployment task as completed."
- Fuzzy matches title, updates status, logs timestamp

### UC-06: Overdue Task Query
> "What are my overdue tasks?"
- Returns tasks past due date, not completed

### UC-07: Proactive Daily Briefing (Autonomous)
- Every morning at 9:00 AM — tasks due today, overdue count, top recommendation

### UC-08: Overdue Follow-up (Autonomous)
- Every evening at 6:00 PM — follow-up for unresolved overdue tasks

### UC-09: Dashboard View
- Filter/search tasks, view details, audit trail

### UC-10: Task Update
> "Update the API testing task deadline to next Monday."

---

## 4. Functional Requirements

### 4.1 Task Management
| ID | Requirement | Priority |
|----|------------|----------|
| FR-01 | Create tasks with title, description, priority, assignee, due date | MUST |
| FR-02 | Update any task field | MUST |
| FR-03 | Delete tasks (soft delete) | MUST |
| FR-04 | Mark tasks as complete | MUST |
| FR-05 | Search tasks by keyword, assignee, status, priority | MUST |
| FR-06 | Filter tasks by date range | MUST |
| FR-07 | Task priority levels: LOW, MEDIUM, HIGH, CRITICAL | MUST |
| FR-08 | Task statuses: TODO, IN_PROGRESS, REVIEW, DONE, CANCELLED | MUST |
| FR-09 | Assign tasks to team members | MUST |
| FR-10 | Task history/audit trail | SHOULD |

### 4.2 Agent Capabilities
| ID | Requirement | Priority |
|----|------------|----------|
| FR-11 | Natural language intent classification | MUST |
| FR-12 | Multi-turn conversation context (memory) | MUST |
| FR-13 | Fuzzy task title matching | MUST |
| FR-14 | User name resolution from partial mentions | MUST |
| FR-15 | Date/time parsing from natural language | MUST |
| FR-16 | Proactive daily briefing generation | MUST |
| FR-17 | Intelligent task prioritization recommendations | SHOULD |
| FR-18 | Duplicate task detection | SHOULD |
| FR-19 | Human-in-the-loop for destructive actions | SHOULD |

### 4.3 Communication
| ID | Requirement | Priority |
|----|------------|----------|
| FR-20 | Google Chat bot webhook handling | MUST |
| FR-21 | Formatted Google Chat card responses | MUST |
| FR-22 | Proactive Google Chat DM messages | MUST |
| FR-23 | Webhook signature verification | MUST |

### 4.4 Dashboard
| ID | Requirement | Priority |
|----|------------|----------|
| FR-24 | Task list with Kanban/table view | MUST |
| FR-25 | Search and filter interface | MUST |
| FR-26 | Task detail panel | MUST |
| FR-27 | Productivity summary charts | SHOULD |
| FR-28 | Real-time task updates (polling) | SHOULD |

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---------|------------|
| **Performance** | API response < 500ms for CRUD; Agent response < 5s for LLM calls |
| **Availability** | 99.5% uptime for webhook handler |
| **Scalability** | Horizontal FastAPI workers; APScheduler for async jobs |
| **Security** | JWT auth, RBAC, webhook signature verification |
| **Observability** | LangSmith tracing, Prometheus metrics |
| **Auditability** | Every mutation logged with user + timestamp |

---

## 6. Success Metrics

| Metric | Target |
|--------|--------|
| Task creation via NL accuracy | >= 90% |
| Intent classification accuracy | >= 95% |
| Agent response time P95 | <= 5 seconds |
| Daily briefing delivery | 100% of active users |
| Dashboard load time | <= 2 seconds |
