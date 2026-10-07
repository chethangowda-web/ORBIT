# ORBIT End-to-End Manual Verification Checklist

**Project:** ORBIT — Multi-Agent AI Task Management System  
**Date:** October 2026  
**Environment:** Local Dev & Docker  

---

## 1. Database & Authentication Setup

| Step | Action | Expected Result | Status |
|------|--------|-----------------|--------|
| 1.1 | Start Postgres & Redis (`docker-compose up -d`) | Containers healthy after 10s | ✅ Verified |
| 1.2 | Run migrations (`alembic upgrade head`) | All 5 tables created without errors | ✅ Verified |
| 1.3 | Seed database (`python -m backend.db.seed`) | 3 users (admin, manager, employee) + 5 tasks created | ✅ Verified |
| 1.4 | Test JWT login (`POST /api/auth/token`) | Returns JWT access token & user profile | ✅ Verified |

---

## 2. Multi-Agent System (LangGraph)

| Step | Action | Expected Result | Status |
|------|--------|-----------------|--------|
| 2.1 | "Create high priority task for John to deploy frontend by Friday" | Intent `CREATE_TASK` → Task created in DB, assigned to John | ✅ Verified |
| 2.2 | "Show my pending tasks" | Intent `GET_MY_TASKS` → Returns list of user's active tasks | ✅ Verified |
| 2.3 | "What should I focus on today?" | Intent `PLAN_DAY` → Returns prioritized list with reasoning | ✅ Verified |
| 2.4 | "Mark CRM deployment as completed" | Intent `COMPLETE_TASK` → Task status updated to `DONE` | ✅ Verified |
| 2.5 | Multi-turn reference: "Delete it" | Review Agent triggers confirmation check (HITL) | ✅ Verified |

---

## 3. Google Chat Integration

| Step | Action | Expected Result | Status |
|------|--------|-----------------|--------|
| 3.1 | Inbound webhook (`POST /api/chat/webhook`) | Returns `200 OK` with status `accepted` | ✅ Verified |
| 3.2 | HMAC signature verification | Invalid signature returns `403 Forbidden` | ✅ Verified |
| 3.3 | Auto-provisioning | First-time Google user created automatically | ✅ Verified |
| 3.4 | Card interaction (`CARD_CLICKED`) | HITL confirmation updates or cancels task | ✅ Verified |

---

## 4. Autonomous Scheduler & Proactive Alerts

| Step | Action | Expected Result | Status |
|------|--------|-----------------|--------|
| 4.1 | Morning Briefing (9 AM IST) | Users receive daily briefing via DM / Space | ✅ Verified |
| 4.2 | Duplicate briefing check | Subsequent runs on same day skip already alerted users | ✅ Verified |
| 4.3 | Overdue Alerts (6 PM IST) | Groups overdue tasks by assignee and dispatches alerts | ✅ Verified |
| 4.4 | Admin trigger endpoint (`POST /api/admin/trigger-briefing`) | Manually triggers briefing and returns summary | ✅ Verified |

---

## 5. Next.js 14 Frontend Dashboard

| Step | Action | Expected Result | Status |
|------|--------|-----------------|--------|
| 5.1 | Visit `http://localhost:3000/login` | Renders dark-mode login form with 1-click test credentials | ✅ Verified |
| 5.2 | Visit `http://localhost:3000` (Dashboard) | Renders Kanban board (TODO, IN_PROGRESS, REVIEW, DONE) & KPIs | ✅ Verified |
| 5.3 | Visit `http://localhost:3000/tasks` | Renders searchable, filterable task table with pagination | ✅ Verified |
| 5.4 | Visit `http://localhost:3000/tasks/[id]` | Shows full task details + audit change timeline | ✅ Verified |
| 5.5 | Visit `http://localhost:3000/analytics` | Renders Recharts completion rate donut, priority bar, team workload | ✅ Verified |
| 5.6 | Visit `http://localhost:3000/settings` | Shows scheduler status & manual trigger buttons | ✅ Verified |
