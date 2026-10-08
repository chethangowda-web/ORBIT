/**
 * ORBIT TypeScript Types and Interfaces
 */

export type UserRole = "employee" | "manager" | "admin";

export type TaskStatus = "TODO" | "IN_PROGRESS" | "REVIEW" | "DONE";

export type TaskPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface User {
  id: string;
  email: string;
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  role: UserRole;
  google_id?: string | null;
  google_space_id?: string | null;
  avatar_url?: string | null;
  timezone: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
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
  assignee?: User | null;
  creator?: User | null;
}

export interface TaskAuditLog {
  id: string;
  task_id: string;
  user_id?: string | null;
  action: string;
  changes?: Record<string, any> | null;
  source: string;
  created_at: string;
  user?: User | null;
}

export interface TaskStats {
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  overdue_tasks: number;
  completion_rate?: number;
  by_status?: Record<TaskStatus, number>;
  by_priority?: Record<TaskPriority, number>;
  tasks_by_status?: Record<string, number>;
  tasks_by_priority?: Record<string, number>;
}

export interface TeamWorkload {
  user_id: string;
  display_name: string;
  email: string;
  role: string;
  assigned_tasks: number;
  completed_tasks: number;
  overdue_tasks: number;
  high_priority_tasks?: number;
  completion_rate?: number;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface APIResponse<T = any> {
  success: boolean;
  data: T;
  meta?: PaginationMeta | Record<string, any> | null;
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
