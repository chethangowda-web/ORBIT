/** Pure helpers that translate between URL search params and API task filters. */

import { ALL_STATUSES, PRIORITIES } from "@/lib/constants";
import type { TaskFilters, TaskPriority, TaskStatus } from "@/types";

export interface TaskView {
  q: string;
  status: TaskStatus | "";
  priority: TaskPriority | "";
  assignee: string; // user id, "me", or ""
  overdue: boolean;
  sortBy: NonNullable<TaskFilters["sort_by"]>;
  sortDir: "asc" | "desc";
  page: number;
}

export const DEFAULT_VIEW: TaskView = {
  q: "",
  status: "",
  priority: "",
  assignee: "",
  overdue: false,
  sortBy: "due_date",
  sortDir: "asc",
  page: 1,
};

const SORT_KEYS = ["due_date", "created_at", "updated_at", "priority", "status", "title"] as const;

export function parseView(params: URLSearchParams): TaskView {
  const status = params.get("status") as TaskStatus | null;
  const priority = params.get("priority") as TaskPriority | null;
  const sortBy = params.get("sort") as TaskView["sortBy"] | null;
  const page = Number(params.get("page"));
  return {
    q: params.get("q") ?? "",
    status: status && ALL_STATUSES.includes(status) ? status : "",
    priority: priority && PRIORITIES.includes(priority) ? priority : "",
    assignee: params.get("assignee") ?? "",
    overdue: params.get("overdue") === "1",
    sortBy: sortBy && (SORT_KEYS as readonly string[]).includes(sortBy) ? sortBy : DEFAULT_VIEW.sortBy,
    sortDir: params.get("dir") === "desc" ? "desc" : "asc",
    page: Number.isInteger(page) && page > 0 ? page : 1,
  };
}

/** Serialise only non-default values so URLs stay short and clean. */
export function serializeView(view: TaskView): string {
  const params = new URLSearchParams();
  if (view.q) params.set("q", view.q);
  if (view.status) params.set("status", view.status);
  if (view.priority) params.set("priority", view.priority);
  if (view.assignee) params.set("assignee", view.assignee);
  if (view.overdue) params.set("overdue", "1");
  if (view.sortBy !== DEFAULT_VIEW.sortBy) params.set("sort", view.sortBy);
  if (view.sortDir !== DEFAULT_VIEW.sortDir) params.set("dir", view.sortDir);
  if (view.page > 1) params.set("page", String(view.page));
  return params.toString();
}

function isoDay(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function toApiFilters(view: TaskView, currentUserId: string | undefined, pageSize: number, now = new Date()): TaskFilters {
  const filters: TaskFilters = {
    q: view.q.trim() || undefined,
    status: view.status ? [view.status] : undefined,
    priority: view.priority ? [view.priority] : undefined,
    assignee_id: view.assignee === "me" ? currentUserId : view.assignee || undefined,
    sort_by: view.sortBy,
    sort_dir: view.sortDir,
    page: view.page,
    page_size: pageSize,
  };
  if (view.overdue) {
    const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    filters.due_before = isoDay(yesterday);
    filters.include_completed = false;
  }
  return filters;
}

export function hasActiveFilters(view: TaskView): boolean {
  return Boolean(view.q || view.status || view.priority || view.assignee || view.overdue);
}

/** Toggle sort: same column flips direction, a new column starts ascending. */
export function nextSort(view: TaskView, column: TaskView["sortBy"]): Pick<TaskView, "sortBy" | "sortDir"> {
  if (view.sortBy === column) return { sortBy: column, sortDir: view.sortDir === "asc" ? "desc" : "asc" };
  return { sortBy: column, sortDir: "asc" };
}
