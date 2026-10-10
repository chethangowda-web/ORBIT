# ORBIT UI Design System & Architecture Specification
**Document Version:** 1.0.0  
**Phase:** Phase 10 - Product Design System and UI Architecture  
**Author:** Senior Product Designer & Frontend Architect  
**Status:** Design Plan (Pre-Implementation)

---

## 1. Product Identity & Design Direction

### 1.1 Product Identity
ORBIT is a high-reliability, multi-agent autonomous task management and team operations platform. It combines deterministic workflow routing (LangGraph), asynchronous background scheduling (APScheduler), real-time team collaboration (Google Chat webhooks), and human-in-the-loop (HITL) safety verification.

The user interface must convey:
- **Precision & Reliability:** An engineering-grade operational cockpit, not a promotional SaaS marketing website or consumer chat app.
- **Data Authenticity:** 100% of figures, statuses, and charts trace directly to verified PostgreSQL records and live API responses. Zero fabricated metrics or placeholder workstreams.
- **Utility & High Density:** Compact tables, structured Kanban boards, scannable priority/status badges, and clear action triggers over large empty space and decorative art.

### 1.2 Chosen Design Direction
**Primary:** Direction A (Engineering Workspace)  
**Secondary Influence:** Direction B (Developer Operations Console)

Inspired by the focused, quiet utility of Linear and GitHub without mimicry:
- Dark charcoal canvas with subtle slate elevation.
- Single restrained blue accent (`#3B82F6`) reserved strictly for interactive focus, active navigation, and primary actions.
- Thin borders (`#263241`) defining structural hierarchy without heavy drop shadows.
- Clear technical metadata presentation (timings, agent routing traces, exact delivery channels).

### 1.3 Non-Negotiable Visual Invariants
1. **Zero Gradients:** No purple, cyan, or blue-purple background gradients, gradient text, or gradient buttons.
2. **Zero Glowing Effects:** No neon box-shadows, pulsing indicator rings, or ambient blur backdrops.
3. **Restrained Corner Radii:** 
   - Buttons, badges, and form controls: **4px to 6px** (`rounded-md` / `rounded-[5px]`).
   - Cards, panels, modals, and container shells: **6px to 8px** (`rounded-lg` / `rounded-[7px]`).
   - No pill-shaped buttons (`rounded-full` prohibited for buttons, tabs, and action items).
4. **Honest Metrics Only:** No mock numbers, simulated workload counts, or unverified percentages.
5. **Concise Interface Copy:** No vague hero headers or marketing fluff. No em dashes (`—`) anywhere in interface strings.
6. **Zero Emojis:** The interface exclusively utilizes consistent, stroked Lucide icons (`w-3.5 h-3.5` / `w-4 h-4`).
7. **Restrained Motion:** Zero scroll-triggered parallax, bouncing animations, or heavy transitions. Transitions capped at `150ms ease`. Respect `prefers-reduced-motion`.

---

## 2. Design Tokens Specification

### 2.1 Color Palette
All color values are deterministic and mapped into the Tailwind CSS configuration and CSS custom properties.

```css
:root {
  /* Canvas & Surfaces */
  --orbit-bg: #090D13;          /* Main application backdrop */
  --orbit-surface: #111821;     /* Primary surface (cards, sidebar, table wrapper) */
  --orbit-elevated: #151F2C;    /* Secondary/elevated surface (modals, dropdowns, hovered rows) */
  --orbit-border: #263241;      /* Thin structural dividing border */
  --orbit-border-subtle: #1C2633;/* Subtle dividers within panels */

  /* Text & Typography */
  --orbit-text-primary: #E5EAF1;   /* High-contrast headings and primary labels */
  --orbit-text-secondary: #94A3B8; /* Body text, descriptions, inactive icons */
  --orbit-text-muted: #64748B;     /* Captions, timestamps, disabled indicators */

  /* Primary Interactive Accent */
  --orbit-accent: #3B82F6;         /* Primary blue (active state, primary button, focus) */
  --orbit-accent-hover: #2563EB;   /* Primary blue hover */
  --orbit-accent-subtle: rgba(59, 130, 246, 0.12); /* Subtle blue badge/pill backdrop */

  /* Semantic Feedback (Muted & Restrained) */
  --orbit-success: #10B981;        /* Done / Completed / Health OK */
  --orbit-success-subtle: rgba(16, 185, 129, 0.12);
  
  --orbit-warning: #F59E0B;        /* Review / Medium Priority / Action Pending */
  --orbit-warning-subtle: rgba(245, 158, 11, 0.12);
  
  --orbit-danger: #EF4444;         /* Overdue / Critical Priority / Destructive Action */
  --orbit-danger-subtle: rgba(239, 68, 68, 0.12);
  
  --orbit-info: #0EA5E9;           /* In Progress / In Flight Specialization */
  --orbit-info-subtle: rgba(14, 165, 233, 0.12);
}
```

### 2.2 Status & Priority Mapping Matrix

| Entity | Value | Text Color | Border Color | Background Tint |
| :--- | :--- | :--- | :--- | :--- |
| **Status** | `TODO` | `#94A3B8` (slate) | `#263241` | `rgba(148, 163, 184, 0.08)` |
| **Status** | `IN_PROGRESS` | `#38BDF8` (sky) | `rgba(56, 189, 248, 0.3)` | `rgba(56, 189, 248, 0.1)` |
| **Status** | `REVIEW` | `#F59E0B` (amber) | `rgba(245, 158, 11, 0.3)` | `rgba(245, 158, 11, 0.1)` |
| **Status** | `DONE` | `#10B981` (emerald) | `rgba(16, 185, 129, 0.3)` | `rgba(16, 185, 129, 0.1)` |
| **Priority** | `LOW` | `#64748B` (slate) | `#263241` | `rgba(100, 116, 139, 0.08)` |
| **Priority** | `MEDIUM` | `#F59E0B` (amber) | `rgba(245, 158, 11, 0.3)` | `rgba(245, 158, 11, 0.1)` |
| **Priority** | `HIGH` | `#F97316` (orange) | `rgba(249, 115, 22, 0.3)` | `rgba(249, 115, 22, 0.1)` |
| **Priority** | `CRITICAL` | `#EF4444` (red) | `rgba(239, 68, 68, 0.3)` | `rgba(239, 68, 68, 0.1)` |

### 2.3 Typography Scale
- **Font Stack:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Monospace Stack:** `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`
- **Scale:**
  - `Display / Page Title`: `18px (text-lg)` to `20px (text-xl)`, weight `700`, leading `1.2`
  - `Section Header`: `13px (text-xs)` to `14px (text-sm)`, weight `600`, uppercase tracking `0.05em`
  - `Table Headings / Meta`: `11px (text-[11px])`, weight `600`, tracking `0.04em`, uppercase
  - `Body / Cell Text`: `12px (text-xs)`, weight `400` / `500`, leading `1.4`
  - `Caption / Technical Trace`: `10px (text-[10px])` to `11px`, weight `400` / `500`, monospace

### 2.4 Spacing & Geometry Tokens
- **Button Radius:** `rounded-md` (`5px`)
- **Card / Panel Radius:** `rounded-lg` (`7px`)
- **Table Density:**
  - Header padding: `px-3.5 py-2.5`
  - Body row padding: `px-3.5 py-2.5`
- **Form Controls:** Height `32px` (`h-8`), horizontal padding `px-3`, text `12px`

---

## 3. Reusable Component Specifications

### 3.1 Button Hierarchy
1. **Primary Button:**
   - Class: `bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium px-3 py-1.5 rounded-md border border-blue-500/30 transition-colors`
   - Use: Main task creation, search submit, confirm operations.
2. **Secondary / Outline Button:**
   - Class: `bg-slate-900 hover:bg-slate-800 text-slate-200 text-xs font-medium px-3 py-1.5 rounded-md border border-slate-700/80 transition-colors`
   - Use: Filter reset, column task add, task detail view.
3. **Destructive Button:**
   - Class: `bg-rose-950/50 hover:bg-rose-900 text-rose-300 hover:text-white text-xs font-medium px-3 py-1.5 rounded-md border border-rose-800/60 transition-colors`
   - Use: Soft-delete task with confirmation modal.
4. **Ghost / Icon Button:**
   - Class: `p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 transition-colors`
   - Use: Row actions, modal close, panel collapse.

### 3.2 Badges & Labels
- Structure: Rectangular, `rounded-md`, horizontal padding `px-2 py-0.5`, font size `11px font-medium`.
- Status & Priority components enforce the exact matrix defined in Section 2.2.
- No animated pulsing circles or pinging radar dots.

### 3.3 Form Inputs & Selects
- Class: `w-full bg-[#090D13] border border-[#263241] focus:border-[#3B82F6] focus:outline-none rounded-md px-3 py-1.5 text-xs text-[#E5EAF1] placeholder-[#64748B] transition-colors`
- Dropdowns: Custom styled dark select with slate border, matching input height.

### 3.4 Cards & Structural Panels
- Class: `bg-[#111821] border border-[#263241] rounded-lg p-4`
- Elevated / Nested container: `bg-[#151F2C] border border-[#263241] rounded-md p-3`
- No glassmorphic blur with high white opacity; solid, high-legibility dark theme surfaces.

### 3.5 Tables
- Header: `bg-[#0D131A] border-b border-[#263241] text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider`
- Rows: `hover:bg-[#151F2C]/60 border-b border-[#1C2633] transition-colors`
- Empty state: Border dashed `#263241`, centered text `#64748B`.

---

## 4. Screen Layout & Navigation Architecture

### 4.1 Global Layout Shell
- Two-column responsive architecture:
  - **Sidebar:** Width `220px` (`w-56`), fixed left, background `#111821`, border-r `#263241`.
  - **Navbar / Header:** Height `48px` (`h-12`), sticky top, background `#111821`, border-b `#263241`.
  - **Main Content Area:** Flex column, background `#090D13`, scrollable `overflow-y-auto`.
  - **Floating Ops Panel:** Ask ORBIT launcher anchored to `bottom-5 right-5`.

### 4.2 Screen Specifications

#### 01. Login (`/login`)
- **Structure:** Clean centered card (`w-full max-w-sm`), background `#111821`, border `#263241`.
- **Header:** Bot icon in `#151F2C` container, title `ORBIT`, subtitle `Task Management & Autonomous Orchestration`.
- **Form:** Work email input, password input, sign in button (`bg-blue-600`).
- **Demo Selector:** 3 compact buttons for database-seeded accounts:
  1. `admin@orbit.dev` (System Admin)
  2. `sarah@orbit.dev` (Sarah Connor, Manager)
  3. `john@orbit.dev` (John Doe, 13 Tasks)
- **Informative Note:** Explicit caption stating Google Chat accounts authenticate via Google Chat webhooks.

#### 02. Dashboard & Kanban (`/`)
- **Summary Metrics Row:** Single compact 4-column row (`Total Tasks`, `In Progress`, `Completed`, `Overdue`).
  - Strict database tracing: Values bind directly to `api.analytics.stats()`.
- **Kanban Board:**
  - 4 status lanes: `TODO`, `IN_PROGRESS`, `REVIEW`, `DONE`.
  - Column header with lane name, count badge, and plus action button.
  - Cards feature task title (blue hover), priority badge, deadline (red border if overdue), assignee avatar initial, and advance status button.

#### 03. Tasks Management (`/tasks`)
- **Filter Bar:** Search input, status dropdown, priority dropdown, assignee dropdown, reset button.
- **Table:** Details, Status, Priority, Assignee, Due Date, and Actions (`Mark Done`, `View`, `Delete`).
- **Pagination:** Explicit page number, total task count, page size indicator.

#### 04. Analytics & Database Metrics (`/analytics`)
- **Top KPI Cards:**
  1. `Completion Rate`: `{completed} of {total} tasks resolved`
  2. `In Progress Tasks`: Active count from database
  3. `Assigned Team Members`: Active count from database
- **Charts (Recharts):**
  - Donut Chart: Status distribution (`#94A3B8`, `#38BDF8`, `#F59E0B`, `#10B981`).
  - Bar Chart: Tasks by priority level (`#3B82F6`).
  - Horizontal Bar Chart: Team workload distribution with assigned, completed, and overdue bars.
  - Labeled axes, solid tooltip `#111821`, explicit empty states when no tasks match.

#### 05. Settings & Operational Health (`/settings`)
- **User Profile:** Display name, email, role, timezone (`Asia/Kolkata`), Google Chat user ID.
- **Autonomous Background Scheduler:**
  - Status indicator: `Scheduler Running` or `Scheduler Idle`.
  - Manual triggers: `Morning Briefing`, `Overdue Alerts`, `Weekly Summary`.
  - Configured jobs table: Job name, ID, next execution timestamp.
- **System Operational Status:**
  - LangGraph router status, Google Chat webhook status, PostgreSQL database connection.

#### 06. Ask ORBIT (AI Command Center)
- **Launcher:** Compact rectangular trigger (`bg-[#111821] border-[#263241] text-[#E5EAF1]`).
- **Drawer:** Width `420px`, height `580px`, header with reset and minimize controls.
- **Chat Feed:** User bubbles (`bg-blue-600`), assistant bubbles (`bg-[#111821] border-[#263241]`).
- **HITL Safeguard:** Amber approval card (`bg-amber-950/40 border-amber-500/30`) for destructive operations with `Confirm` / `Cancel` buttons.
- **Execution Inspector:** Collapsible trace summary showing routed agents, tool calls, and millisecond timings.

---

## 5. State Handling Rules

| State | Pattern & Treatment |
| :--- | :--- |
| **Loading** | Restrained spinner (`w-4 h-4 border-2 border-blue-500 border-t-transparent animate-spin`) with specific text (`Loading database tasks...`). No full-screen blocking curtains. |
| **Empty** | Border dashed `#263241`, rounded-md, text `#94A3B8`, concise explanation, and relevant CTA (`Create task` or `Clear filters`). |
| **Error** | Red surface `bg-rose-950/50 border border-rose-800/60 text-rose-200 text-xs`, accompanied by actionable retry or error description. |
| **Success** | Subtle banner `bg-emerald-950/40 border border-emerald-800/50 text-emerald-300 text-xs` with `CheckCircle2` icon. |
| **Disabled** | Opacity 50%, cursor not-allowed, pointer-events guarded. |

---

## 6. Audit of Inconsistent Styling & Root Cause Analysis

### 6.1 Diagnosis: The Root Causes
An empirical audit of the frontend directory reveals four distinct root causes behind earlier regressions:

1. **Next.js Dev Server / Build Cache Contention:**
   - **Evidence:** During earlier phases, executing `npm run build` (`next build`) in a parallel process while `npm run dev` was running wiped out the development bundler's in-memory chunk cache in `.next/`.
   - **Impact:** The running dev server returned HTTP `404` for `layout.css` and client chunks (`main-app.js`, `app-pages-internals.js`), causing the browser to render raw unstyled HTML (Times New Roman, zero styling) and un-hydrated React markup ("Loading board tasks...").
   - **Resolution Rule:** Never execute `next build` concurrently over an active `next dev` process without immediately flushing and restarting the server.

2. **Absence of Centralized Design Tokens in Tailwind:**
   - **Evidence:** `tailwind.config.ts` only had `background: "var(--background)"` and `foreground: "var(--foreground)"`. It lacked named tokens for surfaces, borders, and text hierarchy.
   - **Impact:** Developers wrote ad-hoc classes across components (some with `bg-slate-900`, some with `bg-slate-950`, some with `bg-indigo-900`, some with inline hexes).

3. **Stale Inline Classes & Global Gradient Utilities:**
   - **Evidence:** `app/globals.css` contained legacy `.glow-primary` (indigo box-shadow) and `.glow-cyan` utilities. `login/page.tsx` contained inline background blur blobs and gradient buttons.
   - **Impact:** While inner dashboard pages received partial updates, the login page and drawer retained legacy purple/cyan styling.

4. **Authentication Model Divergence (Google Chat vs Database Accounts):**
   - **Evidence:** Google Chat users (e.g. `chethangowdaa1328@gmail.com`) are dynamically provisioned via Chat webhooks with `hashed_password = None`. Attempting password login via `/api/auth/token` correctly fails with 401 Unauthorized.
   - **Impact:** Login demo buttons that attempted to sign in with Google Chat email addresses threw authentication errors. Seeded accounts (`admin@orbit.dev`, `sarah@orbit.dev`, `john@orbit.dev`) authenticate with 200 OK using `password123`.

---

## 7. Target Frontend Files for Implementation

The unified redesign strictly touches frontend presentation files. Backend APIs, LangGraph agents, Redis checkpoints, PostgreSQL schemas, and Google Chat handlers remain 100% untouched.

1. `frontend/tailwind.config.ts`: Define core semantic tokens (`orbit-bg`, `orbit-surface`, `orbit-elevated`, `orbit-border`, `orbit-accent`, `orbit-text`).
2. `frontend/app/globals.css`: Clean up base variables, remove glow classes, enforce consistent body typography.
3. `frontend/app/layout.tsx`: Remove em dashes from metadata, apply root background `#090D13`.
4. `frontend/components/Sidebar.tsx`: Enforce compact `#111821` sidebar, `#263241` borders, Lucide icons, remove em dashes.
5. `frontend/components/Navbar.tsx`: Enforce `#111821` header, clean breadcrumbs, standard 4–6px action buttons.
6. `frontend/components/StatusBadge.tsx`: Enforce 4–6px rectangular badges with exact status color matrix.
7. `frontend/components/PriorityBadge.tsx`: Enforce 4–6px rectangular badges with exact priority color matrix.
8. `frontend/components/KanbanColumn.tsx`: Standardize column headers, task counters, and lane empty states.
9. `frontend/components/TaskCard.tsx`: Standardize task cards with clear overdue indicators and blue hover accents.
10. `frontend/components/TaskTable.tsx`: High-density table styling with clean headers and action buttons.
11. `frontend/components/FilterBar.tsx` & `SearchBar.tsx`: Standardized inputs, dropdowns, and reset buttons.
12. `frontend/components/CreateTaskModal.tsx`: Standardized modal shell, form fields, and action buttons.
13. `frontend/components/AskOrbit.tsx`: Clean ops drawer, structured agent trace inspector, amber HITL cards.
14. `frontend/app/login/page.tsx`: Standardized `#111821` login card, verified demo accounts.
15. `frontend/app/page.tsx` (Dashboard): Compact summary metric row and Kanban board.
16. `frontend/app/tasks/page.tsx`: High-density tasks view.
17. `frontend/app/tasks/[id]/page.tsx`: Structured task details and audit timeline.
18. `frontend/app/analytics/page.tsx`: Database metrics, Recharts color alignment, and empty states.
19. `frontend/app/settings/page.tsx`: Scheduler health, delivery state distinctions, system status.

---

## 8. Phased Implementation & Verification Plan

### Phase 1: Design System Foundation
- Update `tailwind.config.ts` with exact color, radius, and surface tokens.
- Refactor `app/globals.css` to remove legacy glow and gradient definitions.
- Update `app/layout.tsx` metadata and typography.

### Phase 2: Navigation & Component Primitives
- Refactor `Sidebar.tsx` and `Navbar.tsx`.
- Refactor `StatusBadge.tsx` and `PriorityBadge.tsx`.
- Refactor `SearchBar.tsx`, `FilterBar.tsx`, and `Pagination.tsx`.

### Phase 3: Core Workspace Screens
- Refactor `app/login/page.tsx`.
- Refactor `KanbanColumn.tsx`, `TaskCard.tsx`, and `app/page.tsx`.
- Refactor `TaskTable.tsx`, `CreateTaskModal.tsx`, and `app/tasks/page.tsx`.
- Refactor `app/tasks/[id]/page.tsx`.

### Phase 4: Operations & Analytics
- Refactor `AskOrbit.tsx`.
- Refactor `app/analytics/page.tsx`.
- Refactor `app/settings/page.tsx`.

### Phase 5: Verification & Browser Testing
1. **Build Validation:** Run `npm run build` in `frontend/` to confirm 0 TypeScript / lint errors.
2. **Runtime Restart:** Clean `.next` and start `npm run dev` to ensure no stale chunk 404s.
3. **Browser Verification:**
   - Verify `/login` with `admin@orbit.dev`, `sarah@orbit.dev`, and `john@orbit.dev`.
   - Verify `/` Kanban lanes, task advance, and compact metrics row.
   - Verify `/tasks` search, filter, detail navigation, and soft-delete confirmation.
   - Verify `/analytics` database counts and chart tooltips.
   - Verify `/settings` scheduler health and trigger buttons.
   - Verify Ask ORBIT drawer, trace inspector, and HITL cancellation/confirmation.
4. **Backend Regression:** Run `pytest tests/` (81/81 passing).

---

## 9. Risk Matrix & Safeguards

| Risk | Likelihood | Impact | Mitigation Safeguard |
| :--- | :---: | :---: | :--- |
| **Dev server 404 chunk collision** | Medium | High | Never run `next build` concurrently while serving dev traffic. Flush `.next` whenever switching between dev and production modes. |
| **Authentication state loss** | Low | High | Preserve `orbit_token` and `orbit_user` in `localStorage` and `cookie`. Interceptor logic in `api-client.ts` remains untouched. |
| **API query breakage** | Low | High | Zero modifications to TanStack Query keys, mutation functions, or Axios endpoints. Only JSX layout and Tailwind classes are refined. |
| **Unlinked Google Chat users** | Medium | Low | Clearly distinguish Google Chat webhook identities from database password accounts on the login screen. |
