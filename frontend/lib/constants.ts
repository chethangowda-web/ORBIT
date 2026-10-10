import type { TaskPriority, TaskStatus, UserRole } from "@/types";

/** Board lanes, in workflow order. CANCELLED tasks live outside the board. */
export const BOARD_STATUSES: TaskStatus[] = ["TODO", "IN_PROGRESS", "REVIEW", "DONE"];

export const ALL_STATUSES: TaskStatus[] = [...BOARD_STATUSES, "CANCELLED"];

export const PRIORITIES: TaskPriority[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const STATUS_LABEL: Record<TaskStatus, string> = {
  TODO: "To do",
  IN_PROGRESS: "In progress",
  REVIEW: "Review",
  DONE: "Done",
  CANCELLED: "Cancelled",
};

export const PRIORITY_LABEL: Record<TaskPriority, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

/** Semantic color token (Tailwind color name) for each status and priority. */
export const STATUS_TONE: Record<TaskStatus, "muted" | "info" | "warn" | "ok" | "faint"> = {
  TODO: "muted",
  IN_PROGRESS: "info",
  REVIEW: "warn",
  DONE: "ok",
  CANCELLED: "faint",
};

export const PRIORITY_TONE: Record<TaskPriority, "danger" | "high" | "warn" | "faint"> = {
  CRITICAL: "danger",
  HIGH: "high",
  MEDIUM: "warn",
  LOW: "faint",
};

/** Hex values for charts (Recharts needs literal colors); mirrors the CSS tokens. */
export const CHART_COLORS = {
  accent: "#4C8DFF",
  ok: "#34C38F",
  warn: "#F5A524",
  danger: "#F0546A",
  info: "#3FB6E8",
  high: "#F2812E",
  muted: "#97A3B6",
  faint: "#7C8AA3",
  grid: "#1A2330",
  surface: "#1D2633",
  line: "#243040",
} as const;

export const STATUS_CHART_COLOR: Record<TaskStatus, string> = {
  TODO: CHART_COLORS.muted,
  IN_PROGRESS: CHART_COLORS.info,
  REVIEW: CHART_COLORS.warn,
  DONE: CHART_COLORS.ok,
  CANCELLED: CHART_COLORS.faint,
};

export const PRIORITY_CHART_COLOR: Record<TaskPriority, string> = {
  CRITICAL: CHART_COLORS.danger,
  HIGH: CHART_COLORS.high,
  MEDIUM: CHART_COLORS.warn,
  LOW: CHART_COLORS.faint,
};

export const ROLE_LABEL: Record<UserRole, string> = {
  admin: "Admin",
  manager: "Manager",
  employee: "Employee",
};

/** Tasks move one step along this path when "advanced" from the board. */
export const NEXT_STATUS: Partial<Record<TaskStatus, TaskStatus>> = {
  TODO: "IN_PROGRESS",
  IN_PROGRESS: "REVIEW",
  REVIEW: "DONE",
};

export const NOTIFICATION_TYPE_LABEL: Record<string, string> = {
  daily_briefing: "Daily briefing",
  overdue_alert: "Overdue alert",
  weekly_summary: "Weekly summary",
  task_assigned: "Task assigned",
  task_updated: "Task updated",
  task_completed: "Task completed",
  task_commented: "New comment",
};

export const AGENT_LABEL: Record<string, string> = {
  supervisor: "Supervisor",
  task_agent: "Tasks",
  planner_agent: "Planner",
  recommendation_agent: "Insights",
  review_agent: "Review",
};
