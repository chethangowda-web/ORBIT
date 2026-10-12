/** Pure formatting helpers (no React) so they are trivially unit-testable. */

import { PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import type { Task, TaskAuditLog } from "@/types";

/** Parse a YYYY-MM-DD date as a local calendar date (never shifted by timezone). */
export function parseDateOnly(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function startOfToday(now: Date = new Date()): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/** Whole days from today until the due date (negative when past due). */
export function daysUntil(due: string, now: Date = new Date()): number {
  const ms = parseDateOnly(due).getTime() - startOfToday(now).getTime();
  return Math.round(ms / 86_400_000);
}

export function isOverdue(task: Pick<Task, "due_date" | "status">, now: Date = new Date()): boolean {
  if (!task.due_date) return false;
  if (task.status === "DONE" || task.status === "CANCELLED") return false;
  return daysUntil(task.due_date, now) < 0;
}

/** "Today", "Tomorrow", "3d overdue", "in 5d", or a short date for far-off dates. */
export function formatDue(due: string, now: Date = new Date()): string {
  const days = daysUntil(due, now);
  if (days === 0) return "Today";
  if (days === 1) return "Tomorrow";
  if (days === -1) return "1d overdue";
  if (days < 0) return `${Math.abs(days)}d overdue`;
  if (days <= 14) return `in ${days}d`;
  return parseDateOnly(due).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "None";
  const d = value.length === 10 ? parseDateOnly(value) : new Date(value);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "just now", "5m ago", "3h ago", "2d ago". */
export function timeAgo(value: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(value).getTime()) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function formatMs(ms: number | undefined | null): string {
  if (ms == null) return "";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

export function percent(fraction: number | undefined | null): string {
  return `${Math.round((fraction ?? 0) * 100)}%`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function initials(name: string | undefined | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Humanise a snake/upper case identifier: IN_PROGRESS -> "In progress". */
export function humanize(value: string): string {
  const spaced = value.replace(/_/g, " ").toLowerCase();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function renderChangeValue(field: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "none";
  if (typeof value === "string") {
    // Use the same wording as the rest of the UI ("To do", not "Todo").
    if (field === "status" && value in STATUS_LABEL) return STATUS_LABEL[value as keyof typeof STATUS_LABEL];
    if (field === "priority" && value in PRIORITY_LABEL) return PRIORITY_LABEL[value as keyof typeof PRIORITY_LABEL];
    if (/^[A-Z_]+$/.test(value)) return humanize(value);
  }
  return String(value);
}

const FIELD_LABEL: Record<string, string> = {
  assignee_id: "assignee",
  due_date: "due date",
  completed_at: "completion",
  deleted_at: "deletion",
  completion_note: "completion note",
};

/** Turn an audit entry into a readable sentence instead of raw JSON. */
export function describeAudit(log: Pick<TaskAuditLog, "action" | "changes" | "user" | "source">): string {
  const actor = log.user?.display_name ?? (log.source === "scheduler" ? "ORBIT" : "Someone");
  switch (log.action) {
    case "CREATED":
      return `${actor} created the task`;
    case "COMPLETED":
      return `${actor} marked the task done`;
    case "DELETED":
      return `${actor} deleted the task`;
    case "COMMENTED":
      return `${actor} commented`;
    case "ATTACHED":
      return `${actor} attached ${log.changes?.attachment?.new ?? "a file"}`;
    case "ATTACHMENT_REMOVED":
      return `${actor} removed ${log.changes?.attachment?.old ?? "a file"}`;
  }
  const entries = Object.entries(log.changes ?? {}).filter(([field]) => field !== "completed_at");
  if (entries.length === 0) return `${actor} updated the task`;
  const parts = entries.map(([field, change]) => {
    const label = FIELD_LABEL[field] ?? field.replace(/_/g, " ");
    if (field === "assignee_id") {
      return change.new ? "changed the assignee" : "unassigned the task";
    }
    return `changed ${label} from ${renderChangeValue(field, change.old)} to ${renderChangeValue(field, change.new)}`;
  });
  return `${actor} ${parts.join(", ")}`;
}

export function sourceLabel(source: string): string {
  switch (source) {
    case "chat":
      return "Google Chat";
    case "api":
      return "Dashboard";
    case "scheduler":
      return "Automatic";
    default:
      return humanize(source);
  }
}
