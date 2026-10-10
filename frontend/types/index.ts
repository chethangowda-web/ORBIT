/**
 * ORBIT TypeScript types. These mirror the backend schemas (backend/schemas/*).
 */

export type UserRole = "employee" | "manager" | "admin";

export type TaskStatus = "TODO" | "IN_PROGRESS" | "REVIEW" | "DONE" | "CANCELLED";

export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

/** Directory view returned for assignees, creators and user lists. */
export interface UserPublic {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  avatar_url?: string | null;
  is_active: boolean;
}

/** Full profile returned for the signed-in user and, to managers, for any user. */
export interface User extends UserPublic {
  first_name?: string | null;
  last_name?: string | null;
  google_id?: string | null;
  google_space_id?: string | null;
  timezone: string;
  last_seen_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

/** Minimal user returned inside auth token responses. */
export interface SessionUser {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  google_space_id?: string | null;
}

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assignee_id?: string | null;
  created_by_id: string;
  due_date?: string | null;
  completed_at?: string | null;
  deleted_at?: string | null;
  tags?: string[];
  created_at: string;
  updated_at: string;
  days_overdue?: number | null;
  assignee?: UserPublic | null;
  creator?: UserPublic | null;
}

export interface TaskAuditLog {
  id: string;
  task_id: string;
  user_id?: string | null;
  action: string;
  changes?: Record<string, { old?: unknown; new?: unknown }> | null;
  source: string;
  created_at: string;
  user?: UserPublic | null;
}

export interface TaskStats {
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  overdue_tasks: number;
  completion_rate: number;
  avg_completion_days: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  tasks_created_per_day: { date: string; count: number }[];
}

export interface TeamWorkload {
  user_id: string;
  display_name: string;
  email: string;
  role: string;
  assigned_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  high_priority_tasks: number;
  completion_rate: number;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface APIResponse<T = unknown> {
  success: boolean;
  data: T;
  meta?: PaginationMeta | Record<string, unknown> | null;
  error?: string | null;
}

export interface ScheduledJob {
  id: string;
  name: string;
  next_run_time: string | null;
  trigger: string;
}

export interface SchedulerStatus {
  running: boolean;
  job_count: number;
  jobs: ScheduledJob[];
  timezone: string;
}

export interface NotificationLogEntry {
  id: string;
  user_id: string;
  user_name: string;
  type: string;
  status: "sent" | "failed" | "skipped";
  message: string;
  error_msg?: string | null;
  sent_at: string;
}

export interface HealthStatus {
  status: string;
  database: string;
  redis: string;
  checkpoint?: { backend: string; is_durable: boolean; connected: boolean; mode: string };
}

export interface ChatExecutionMetadata {
  request_id?: string | null;
  active_agent?: string | null;
  agents_invoked?: string[];
  intent?: string | null;
  confidence?: number | null;
  tool_calls_made: string[];
  node_durations_ms?: Record<string, number>;
  total_duration_ms?: number;
  status?: string;
}

export interface AgentExecutionTrace {
  id: string;
  request_id: string;
  user_id: string;
  thread_id: string;
  intent?: string | null;
  confidence?: number | null;
  active_agent?: string | null;
  agents_invoked: string[];
  tool_calls_made: string[];
  node_durations_ms: Record<string, number>;
  total_duration_ms: number;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  started_at: string;
  completed_at: string;
  created_at: string;
}

export interface ReferencedTask {
  id: string;
  title: string;
  status?: string | null;
  priority?: string | null;
  due_date?: string | null;
  assignee_name?: string | null;
}

export interface ChatQueryRequest {
  message: string;
  thread_id?: string;
  confirmed?: boolean;
}

export interface ChatQueryResponse {
  response: string;
  thread_id: string;
  message_id: string;
  needs_confirmation: boolean;
  referenced_task_id?: string | null;
  referenced_tasks: ReferencedTask[];
  suggested_actions: string[];
  metadata: ChatExecutionMetadata;
}

export interface TaskFilters {
  q?: string;
  status?: TaskStatus[];
  priority?: TaskPriority[];
  assignee_id?: string;
  due_before?: string;
  sort_by?: "due_date" | "created_at" | "updated_at" | "priority" | "status" | "title";
  sort_dir?: "asc" | "desc";
  include_completed?: boolean;
  page?: number;
  page_size?: number;
}
