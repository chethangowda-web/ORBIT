/**
 * ORBIT REST API client.
 *
 * Typed Axios instance that injects the JWT, unwraps the `{success, data, meta, error}`
 * envelope, and raises `ApiError` (with HTTP status and server metadata) on failure.
 */

import axios, { AxiosError } from "axios";
import type {
  AgentExecutionTrace,
  APIResponse,
  BulkAction,
  BulkResult,
  ChatQueryRequest,
  ChatQueryResponse,
  HealthStatus,
  IntegrationsStatus,
  NotificationLogEntry,
  PaginationMeta,
  SchedulerStatus,
  SessionUser,
  SimilarTask,
  AssigneeSuggestion,
  WeekPlan,
  Task,
  TaskAttachment,
  TaskAuditLog,
  TaskComment,
  TaskFilters,
  TaskStats,
  TeamWorkload,
  User,
  UserPublic,
  UserRole,
} from "@/types";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api";

export const TOKEN_KEY = "orbit_token";
export const USER_KEY = "orbit_user";
export const AUTH_EVENT = "orbit:auth-expired";

/** Error raised for any non-2xx API response or network failure. */
export class ApiError extends Error {
  readonly status: number;
  readonly meta: Record<string, unknown> | null;

  constructor(message: string, status = 0, meta: Record<string, unknown> | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.meta = meta;
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
  // FastAPI expects repeated keys (status=A&status=B), not status[]=A.
  paramsSerializer: { indexes: null },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<APIResponse<unknown>>) => {
    const status = error.response?.status ?? 0;
    const body = error.response?.data;

    if (status === 401 && typeof window !== "undefined") {
      const onAuthPage = ["/login"].includes(window.location.pathname);
      if (!onAuthPage) window.dispatchEvent(new Event(AUTH_EVENT));
    }

    const message =
      (typeof body?.error === "string" && body.error) ||
      (status === 0 ? "Cannot reach the ORBIT server. Check your connection." : error.message) ||
      "Something went wrong.";
    const meta = body?.meta && !("page" in body.meta) ? (body.meta as Record<string, unknown>) : null;
    return Promise.reject(new ApiError(message, status, meta));
  },
);

type Paged<T> = { items: T[]; meta: PaginationMeta };

const EMPTY_META: PaginationMeta = { page: 1, page_size: 20, total: 0, total_pages: 0 };

const unwrap = <T>(res: { data: APIResponse<T> }): T => res.data.data;

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: SessionUser;
}

export const api = {
  auth: {
    login: async (email: string, password: string) =>
      unwrap<LoginResult>(await apiClient.post("/auth/token", { email, password })),
    refresh: async () => unwrap<LoginResult>(await apiClient.post("/auth/refresh", {})),
    logout: async () => {
      await apiClient.post("/auth/logout", {}, { withCredentials: true });
    },
    me: async () => unwrap<User>(await apiClient.get("/users/me")),
  },

  tasks: {
    list: async (filters: TaskFilters = {}): Promise<Paged<Task>> => {
      const res = await apiClient.get<APIResponse<Task[]>>("/tasks", { params: filters });
      return { items: res.data.data ?? [], meta: (res.data.meta as PaginationMeta) ?? EMPTY_META };
    },
    get: async (id: string) => unwrap<Task>(await apiClient.get(`/tasks/${id}`)),
    create: async (body: {
      title: string;
      description?: string;
      priority?: string;
      assignee_id?: string | null;
      due_date?: string | null;
      tags?: string[];
    }) => unwrap<Task>(await apiClient.post("/tasks", body)),
    update: async (
      id: string,
      body: Partial<{
        title: string;
        description: string | null;
        status: string;
        priority: string;
        assignee_id: string | null;
        due_date: string | null;
        tags: string[];
      }>,
    ) => unwrap<Task>(await apiClient.patch(`/tasks/${id}`, body)),
    complete: async (id: string) => unwrap<Task>(await apiClient.post(`/tasks/${id}/complete`)),
    remove: async (id: string) => unwrap<{ message: string }>(await apiClient.delete(`/tasks/${id}`)),
    history: async (id: string) => (unwrap<TaskAuditLog[]>(await apiClient.get(`/tasks/${id}/history`)) ?? []),
    comments: async (id: string) => (unwrap<TaskComment[]>(await apiClient.get(`/tasks/${id}/comments`)) ?? []),
    addComment: async (id: string, body: string) =>
      unwrap<TaskComment>(await apiClient.post(`/tasks/${id}/comments`, { body })),
    deleteComment: async (id: string, commentId: string) =>
      unwrap<{ message: string }>(await apiClient.delete(`/tasks/${id}/comments/${commentId}`)),
    similar: async (title: string) => (unwrap<SimilarTask[]>(await apiClient.get("/tasks/similar", { params: { title } })) ?? []),
    attachments: async (id: string) => (unwrap<TaskAttachment[]>(await apiClient.get(`/tasks/${id}/attachments`)) ?? []),
    uploadAttachment: async (id: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      // Let the browser set the multipart boundary; the JSON default would break it.
      return unwrap<TaskAttachment>(
        await apiClient.post(`/tasks/${id}/attachments`, form, { headers: { "Content-Type": undefined }, timeout: 120_000 }),
      );
    },
    downloadAttachment: async (id: string, attachmentId: string) =>
      (await apiClient.get<Blob>(`/tasks/${id}/attachments/${attachmentId}`, { responseType: "blob", timeout: 120_000 })).data,
    deleteAttachment: async (id: string, attachmentId: string) =>
      unwrap<{ message: string }>(await apiClient.delete(`/tasks/${id}/attachments/${attachmentId}`)),
    bulk: async (taskIds: string[], action: BulkAction, value?: string) =>
      unwrap<BulkResult>(await apiClient.post("/tasks/bulk", { task_ids: taskIds, action, value })),
  },

  users: {
    list: async (params: { q?: string; role?: string; is_active?: boolean; page?: number; page_size?: number } = {}) => {
      const res = await apiClient.get<APIResponse<UserPublic[]>>("/users", { params });
      return { items: res.data.data ?? [], meta: (res.data.meta as PaginationMeta) ?? EMPTY_META } as Paged<UserPublic>;
    },
    get: async (id: string) => unwrap<User | UserPublic>(await apiClient.get(`/users/${id}`)),
    updateMe: async (body: { display_name?: string; first_name?: string; last_name?: string; timezone?: string }) =>
      unwrap<User>(await apiClient.patch("/users/me", body)),
    preferences: async () => unwrap<Record<string, string>>(await apiClient.get("/users/me/preferences")),
    updatePreferences: async (preferences: Record<string, string>) =>
      unwrap<{ message: string }>(await apiClient.patch("/users/me/preferences", { preferences })),
    adminUpdate: async (id: string, body: { role?: UserRole; is_active?: boolean }) =>
      unwrap<User>(await apiClient.patch(`/users/${id}`, body)),
  },

  planning: {
    week: async () => unwrap<WeekPlan>(await apiClient.get("/planning/week")),
    suggestAssignee: async () => (unwrap<AssigneeSuggestion[]>(await apiClient.get("/planning/suggest-assignee", { params: { limit: 3 } })) ?? []),
  },

  analytics: {
    stats: async () => unwrap<TaskStats>(await apiClient.get("/analytics/stats")),
    workload: async () => (unwrap<TeamWorkload[]>(await apiClient.get("/analytics/team-workload")) ?? []),
  },

  admin: {
    schedulerStatus: async () => unwrap<SchedulerStatus>(await apiClient.get("/admin/scheduler/status")),
    trigger: async (job: "briefing" | "overdue" | "weekly" | "dueSoon" | "stale" | "escalation") => {
      const path = {
        briefing: "/admin/trigger-briefing",
        overdue: "/admin/trigger-overdue-alerts",
        weekly: "/admin/trigger-weekly-summary",
        dueSoon: "/admin/trigger-due-soon",
        stale: "/admin/trigger-stale-nudges",
        escalation: "/admin/trigger-escalations",
      }[job];
      return unwrap<Record<string, number>>(await apiClient.post(path, null, { params: { force: true } }));
    },
    integrations: async () => unwrap<IntegrationsStatus>(await apiClient.get("/admin/integrations")),
    notifications: async (params: { status?: string; type?: string; page?: number; page_size?: number } = {}) => {
      const res = await apiClient.get<APIResponse<NotificationLogEntry[]>>("/admin/notifications", { params });
      return { items: res.data.data ?? [], meta: (res.data.meta as PaginationMeta) ?? EMPTY_META } as Paged<NotificationLogEntry>;
    },
  },

  chat: {
    query: async (payload: ChatQueryRequest) =>
      unwrap<ChatQueryResponse>(await apiClient.post("/chat/query", payload)),
    traces: async (params: { limit?: number; offset?: number } = {}) =>
      unwrap<{ items: AgentExecutionTrace[]; total: number }>(await apiClient.get("/chat/traces", { params })),
    trace: async (id: string) => unwrap<AgentExecutionTrace>(await apiClient.get(`/chat/traces/${id}`)),
  },

  health: async () => unwrap<HealthStatus>(await apiClient.get("/health")),
};
