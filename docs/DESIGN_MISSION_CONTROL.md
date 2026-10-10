# ORBIT v2 Design: Mission Control

A dark, dense, data-first operations console. The dashboard is a flight deck for
the agents and the work they manage. Every number comes from the API; nothing is
decorative.

## Principles
1. **Tokens only.** Components never use raw hex or Tailwind palette colors. All
   color, radius, spacing and type come from the tokens below.
2. **Density with hierarchy.** Compact rows, mono numerals, one accent. Hierarchy
   comes from weight, size and surface level, not color noise.
3. **Keyboard first.** Ctrl+K command palette is the primary navigation and
   action surface. Every action reachable from the palette.
4. **Live by default.** Task data polls; agent activity streams into the right rail.
5. **Honest states.** Loading uses skeletons, empty states say what to do, errors
   say what failed and offer retry. No fabricated metrics.
6. **No gradients, glows, emojis or em dashes in UI copy.** Icons are Lucide, stroked.

## Tokens (CSS variables, mapped into Tailwind as `bg-surface`, `text-fg-muted`, etc.)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0A0E14` | App background |
| `--surface-1` | `#10151D` | Panels, sidebar, table wrapper |
| `--surface-2` | `#161D28` | Cards, hovered rows, inputs |
| `--surface-3` | `#1D2633` | Popovers, modals, active rows |
| `--line` | `#243040` | Borders |
| `--line-subtle` | `#1A2330` | Inner dividers |
| `--fg` | `#E6EBF2` | Primary text |
| `--fg-muted` | `#97A3B6` | Secondary text |
| `--fg-faint` | `#7C8AA3` | Captions, disabled (about 5:1 on panels; the first draft's `#64718A` failed WCAG AA for small text) |
| `--accent` | `#4C8DFF` | Focus, active nav, primary action |
| `--accent-strong` | `#2F72EB` | Primary hover |
| `--ok` | `#34C38F` | Done, healthy |
| `--warn` | `#F5A524` | Review, medium, pending |
| `--danger` | `#F0546A` | Overdue, critical, destructive |
| `--info` | `#3FB6E8` | In progress, running agent |

Each semantic color has a `-soft` variant at 12% alpha for badge backgrounds.

### Status and priority
| Value | Color token |
|---|---|
| TODO | `fg-muted` |
| IN_PROGRESS | `info` |
| REVIEW | `warn` |
| DONE | `ok` |
| CANCELLED | `fg-faint` |
| LOW | `fg-faint` |
| MEDIUM | `warn` |
| HIGH | orange `#F2812E` (`--high`) |
| CRITICAL | `danger` |

### Geometry and type
- Radius: controls 6px, cards and panels 8px, modals 10px. No pill buttons.
- Control height 32px (compact), 28px (dense table actions).
- Font: the platform UI font stack for text and the platform monospace stack for numerals, ids, timings and trace data. System fonts keep builds free of network font fetches and render instantly.
- Scale: page title 18/600, section label 11/600 uppercase +0.06em,
  body 13/400, table cell 12.5/400, caption 11/400 mono.
- Motion: 120ms ease for color and opacity only. Respect `prefers-reduced-motion`.

## App shell
```
+--------+-----------------------------------------------+------------+
| rail   | topbar: breadcrumb | Ctrl+K | health | user    | AGENT RAIL |
| 56px   +-----------------------------------------------+ 280px,     |
| icons  | page content                                  | collapsible|
+--------+-----------------------------------------------+------------+
```
- **Left rail:** icon navigation with tooltips (Board, Tasks, Insights, Traces,
  Admin). Role-gated at the route level as well as in the UI.
- **Top bar:** breadcrumb, command palette trigger, live health pill bound to
  `/api/health`, user menu.
- **Agent rail:** Ask ORBIT composer plus a live feed of recent agent runs
  (intent, agents invoked, tools, duration). Available on every page.

## Screens
1. **Board** (home, `/`): metric strip (open, in progress, overdue, done) bound to
   `/analytics/stats`; Kanban lanes with drag and drop; quick filters.
2. **Tasks** (`/tasks`): dense table, saved filters, column sorting, bulk complete, inline
   status and priority edit, row detail drawer.
3. **Task detail** (`/tasks/[id]`): page with fields, activity timeline rendered as
   human sentences ("John changed priority MEDIUM to HIGH"), not raw JSON.
4. **Insights** (`/insights`): completion, status mix, priority mix, workload by person,
   overdue aging. Admin and manager only.
5. **Agent runs** (`/traces`): table of agent runs with a waterfall of per-node timing, tools
   called, status and error. Source: `/chat/traces`.
6. **Admin** (`/admin`): scheduler jobs, manual triggers, notification delivery log, users
   and roles. Admin and manager only; user management admin only.
7. **Auth** (`/login`, `/auth/callback`): sign in (Google plus password), account link flow.

## Component kit (`frontend/components/ui`)
Button, IconButton, Input, Select, Textarea, Checkbox, Badge, StatusBadge,
PriorityBadge, Card, Panel, Table, Tabs, Tooltip, Modal, Drawer, Toast,
CommandPalette, Skeleton, EmptyState, ErrorState, Kbd, Avatar, MetricTile.
Pages compose from these only.
