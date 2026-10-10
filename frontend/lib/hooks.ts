"use client";

/** TanStack Query hooks. Every server interaction in the UI goes through these. */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api-client";
import { useAuth } from "./auth";
import { useToast } from "@/components/ui/Toast";
import { summarizeBulk } from "./bulk";
import type { BulkAction, Task, TaskFilters, TaskStatus } from "@/types";

export const POLL_MS = 15_000;

export const keys = {
  tasks: ["tasks"] as const,
  taskList: (filters: TaskFilters) => ["tasks", "list", filters] as const,
  task: (id: string) => ["tasks", "detail", id] as const,
  taskHistory: (id: string) => ["tasks", "history", id] as const,
  comments: (id: string) => ["tasks", "comments", id] as const,
  stats: ["stats"] as const,
  workload: ["workload"] as const,
  users: ["users"] as const,
  traces: ["traces"] as const,
  health: ["health"] as const,
  scheduler: ["scheduler"] as const,
  notifications: ["notifications"] as const,
  preferences: ["preferences"] as const,
};

export function useTasks(filters: TaskFilters, options: { poll?: boolean; enabled?: boolean } = {}) {
  return useQuery({
    queryKey: keys.taskList(filters),
    queryFn: () => api.tasks.list(filters),
    placeholderData: keepPreviousData,
    refetchInterval: options.poll ? POLL_MS : false,
    enabled: options.enabled ?? true,
  });
}

export function useTask(id: string) {
  return useQuery({ queryKey: keys.task(id), queryFn: () => api.tasks.get(id), retry: false });
}

export function useTaskHistory(id: string) {
  return useQuery({ queryKey: keys.taskHistory(id), queryFn: () => api.tasks.history(id) });
}

export function useStats() {
  return useQuery({ queryKey: keys.stats, queryFn: api.analytics.stats, refetchInterval: POLL_MS });
}

export function useWorkload(enabled: boolean) {
  return useQuery({ queryKey: keys.workload, queryFn: api.analytics.workload, enabled });
}

export function useUsers() {
  return useQuery({
    queryKey: keys.users,
    queryFn: async () => (await api.users.list({ page_size: 100 })).items,
    staleTime: 60_000,
  });
}

export function useTraces(limit = 20) {
  return useQuery({
    queryKey: [...keys.traces, limit],
    queryFn: () => api.chat.traces({ limit }),
    refetchInterval: POLL_MS,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: keys.health,
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  });
}

export function useScheduler(enabled: boolean) {
  return useQuery({ queryKey: keys.scheduler, queryFn: api.admin.schedulerStatus, enabled, retry: false });
}

export function useNotifications(params: { status?: string; type?: string; page?: number }, enabled: boolean) {
  return useQuery({
    queryKey: [...keys.notifications, params],
    queryFn: () => api.admin.notifications({ ...params, page_size: 15 }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

/** Refresh everything derived from task data after any task mutation. */
export function useInvalidateTaskData() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: keys.tasks });
    queryClient.invalidateQueries({ queryKey: keys.stats });
    queryClient.invalidateQueries({ queryKey: keys.workload });
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function useCreateTask(onDone?: (task: Task) => void) {
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    mutationFn: api.tasks.create,
    onSuccess: (task) => {
      invalidate();
      toast.success(`Created "${task.title}"`);
      onDone?.(task);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function useUpdateTask(onDone?: (task: Task) => void) {
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof api.tasks.update>[1] }) =>
      api.tasks.update(id, body),
    onSuccess: (task) => {
      invalidate();
      toast.success("Task updated");
      onDone?.(task);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

/**
 * Move a task between board lanes. The card jumps immediately and rolls back if the
 * server rejects the change, so drag and drop feels instant but never lies.
 */
export function useMoveTask() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    // Completing through the dedicated endpoint stamps completed_at and notifies the creator.
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) =>
      status === "DONE" ? api.tasks.complete(id) : api.tasks.update(id, { status }),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: keys.tasks });
      const snapshots = queryClient.getQueriesData<{ items: Task[] }>({ queryKey: ["tasks", "list"] });
      for (const [key, data] of snapshots) {
        if (!data) continue;
        queryClient.setQueryData(key, {
          ...data,
          items: data.items.map((t) => (t.id === id ? { ...t, status } : t)),
        });
      }
      return { snapshots };
    },
    onError: (error, _vars, context) => {
      context?.snapshots.forEach(([key, data]) => queryClient.setQueryData(key, data));
      toast.error(errorMessage(error));
    },
    onSettled: invalidate,
  });
}

export function useCompleteTask() {
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: string) => api.tasks.complete(id),
    onSuccess: (task) => {
      invalidate();
      toast.success(`Completed "${task.title}"`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function useDeleteTask(onDone?: () => void) {
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    mutationFn: (id: string) => api.tasks.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Task deleted");
      onDone?.();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

/** True when the signed-in user may delete tasks (mirrors the backend rule). */
export function useCanDelete(): boolean {
  return useAuth().isManager;
}


export function useComments(taskId: string) {
  return useQuery({ queryKey: keys.comments(taskId), queryFn: () => api.tasks.comments(taskId) });
}

export function useAddComment(taskId: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (body: string) => api.tasks.addComment(taskId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.comments(taskId) });
      void queryClient.invalidateQueries({ queryKey: keys.taskHistory(taskId) });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}

export function useDeleteComment(taskId: string) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (commentId: string) => api.tasks.deleteComment(taskId, commentId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.comments(taskId) }),
    onError: (e) => toast.error(errorMessage(e)),
  });
}

/** Apply one action to many tasks; reports partial failures instead of hiding them. */
export function useBulkAction(onDone?: () => void) {
  const invalidate = useInvalidateTaskData();
  const toast = useToast();
  return useMutation({
    mutationFn: ({ ids, action, value }: { ids: string[]; action: BulkAction; value?: string }) =>
      api.tasks.bulk(ids, action, value),
    onSuccess: (result, vars) => {
      invalidate();
      const summary = summarizeBulk(vars.action, result);
      if (result.failed.length > 0) toast.error(summary);
      else toast.success(summary);
      onDone?.();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}
