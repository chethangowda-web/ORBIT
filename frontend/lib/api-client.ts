/**
 * ORBIT REST API Client
 * Typed Axios instance handling token injection, response envelope unwrapping, and API routes.
 */

import axios, { AxiosError } from "axios";
import {
  APIResponse,
  PaginationMeta,
  SchedulerStatus,
  Task,
  TaskAuditLog,
  TaskStats,
  TeamWorkload,
  User,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach JWT access token to every outgoing request
apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("orbit_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 unauthorized errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<APIResponse>) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const isLoginPath = window.location.pathname === "/login";
      if (!isLoginPath) {
        localStorage.removeItem("orbit_token");
        localStorage.removeItem("orbit_user");
        window.location.href = "/login";
      }
    }
    const errMsg =
      error.response?.data?.error ||
      error.message ||
      "An unexpected network error occurred.";
    return Promise.reject(new Error(errMsg));
  }
);

// ---------------- API Methods ----------------

export const api = {
  // Auth
  auth: {
    login: async (email: string, password: string): Promise<{ access_token: string; token_type: string; user: User }> => {
      const { data } = await apiClient.post<APIResponse<{ access_token: string; token_type: string; user: User }>>(
        "/auth/token",
        { email, password }
      );
      return data.data;
    },
    me: async (): Promise<User> => {
      const { data } = await apiClient.get<APIResponse<User>>("/auth/me");
      return data.data;
    },
  },

  // Tasks
  tasks: {
    list: async (params?: {
      status?: string;
      priority?: string;
      assignee_id?: string;
      q?: string;
      page?: number;
      page_size?: number;
    }): Promise<{ tasks: Task[]; meta: PaginationMeta }> => {
      const { data } = await apiClient.get<APIResponse<Task[]>>("/tasks", { params });
      return {
        tasks: data.data || [],
        meta: (data.meta as PaginationMeta) || { page: 1, page_size: 20, total: 0, total_pages: 0 },
      };
    },
    get: async (id: string): Promise<Task> => {
      const { data } = await apiClient.get<APIResponse<Task>>(`/tasks/${id}`);
      return data.data;
    },
    create: async (taskData: {
      title: string;
      description?: string;
      priority?: string;
      assignee_id?: string;
      due_date?: string;
      tags?: string[];
    }): Promise<Task> => {
      const { data } = await apiClient.post<APIResponse<Task>>("/tasks", taskData);
      return data.data;
    },
    update: async (
      id: string,
      updates: {
        title?: string;
        description?: string;
        status?: string;
        priority?: string;
        assignee_id?: string;
        due_date?: string | null;
        tags?: string[];
      }
    ): Promise<Task> => {
      const { data } = await apiClient.patch<APIResponse<Task>>(`/tasks/${id}`, updates);
      return data.data;
    },
    complete: async (id: string): Promise<Task> => {
      const { data } = await apiClient.post<APIResponse<Task>>(`/tasks/${id}/complete`);
      return data.data;
    },
    delete: async (id: string): Promise<boolean> => {
      const { data } = await apiClient.delete<APIResponse<boolean>>(`/tasks/${id}`);
      return data.data;
    },
    history: async (id: string): Promise<TaskAuditLog[]> => {
      const { data } = await apiClient.get<APIResponse<TaskAuditLog[]>>(`/tasks/${id}/history`);
      return data.data || [];
    },
  },

  // Users
  users: {
    list: async (): Promise<User[]> => {
      const { data } = await apiClient.get<APIResponse<User[]>>("/users");
      return data.data || [];
    },
    get: async (id: string): Promise<User> => {
      const { data } = await apiClient.get<APIResponse<User>>(`/users/${id}`);
      return data.data;
    },
  },

  // Analytics
  analytics: {
    stats: async (params?: { user_id?: string; date_from?: string; date_to?: string }): Promise<TaskStats> => {
      const { data } = await apiClient.get<APIResponse<TaskStats>>("/analytics/stats", { params });
      return data.data;
    },
    workload: async (): Promise<TeamWorkload[]> => {
      const { data } = await apiClient.get<APIResponse<TeamWorkload[]>>("/analytics/team-workload");
      return data.data || [];
    },
  },

  // Admin & Scheduler
  admin: {
    status: async (): Promise<SchedulerStatus> => {
      const { data } = await apiClient.get<APIResponse<SchedulerStatus>>("/admin/scheduler/status");
      return data.data;
    },
    triggerBriefing: async (force: boolean = true): Promise<any> => {
      const { data } = await apiClient.post<APIResponse>(`/admin/trigger-briefing?force=${force}`);
      return data.data;
    },
    triggerOverdue: async (force: boolean = true): Promise<any> => {
      const { data } = await apiClient.post<APIResponse>(`/admin/trigger-overdue-alerts?force=${force}`);
      return data.data;
    },
    triggerWeekly: async (force: boolean = true): Promise<any> => {
      const { data } = await apiClient.post<APIResponse>(`/admin/trigger-weekly-summary?force=${force}`);
      return data.data;
    },
  },
};
