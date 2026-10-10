"use client";

import React, { useMemo, useState } from "react";
import { Bot, Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorState, MetricTile, PageHeader, Skeleton } from "@/components/ui/Primitives";
import { KanbanBoard } from "@/components/tasks/KanbanBoard";
import { useShell } from "@/components/shell/ShellContext";
import { useAgent } from "@/lib/agent-context";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { useMoveTask, useStats, useTasks } from "@/lib/hooks";
import type { Task, TaskStatus } from "@/types";

type Scope = "all" | "mine";

const OPEN_FILTER = { status: ["TODO", "IN_PROGRESS", "REVIEW"] as TaskStatus[], page_size: 100, sort_by: "due_date" as const };
const DONE_FILTER = { status: ["DONE"] as TaskStatus[], page_size: 12, sort_by: "updated_at" as const, sort_dir: "desc" as const };

export default function BoardPage() {
  const { user } = useAuth();
  const { openNewTask } = useShell();
  const { ask } = useAgent();
  const [scope, setScope] = useState<Scope>("all");
  const move = useMoveTask();

  const assignee = scope === "mine" ? user?.id : undefined;
  const open = useTasks({ ...OPEN_FILTER, assignee_id: assignee }, { poll: true });
  const done = useTasks({ ...DONE_FILTER, assignee_id: assignee }, { poll: true });
  const stats = useStats();

  const tasks = useMemo<Task[]>(() => [...(open.data?.items ?? []), ...(done.data?.items ?? [])], [open.data, done.data]);
  const loading = open.isLoading || done.isLoading;
  const error = open.error ?? done.error;
  const totalTasks = (open.data?.meta.total ?? 0) + (done.data?.meta.total ?? 0);

  const openCount = (stats.data?.total_tasks ?? 0) - (stats.data?.completed_tasks ?? 0) - (stats.data?.by_status?.CANCELLED ?? 0);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        title="Board"
        description="Drag cards between lanes, or use the arrow on a card. Updates here are audited and sent to Google Chat."
        actions={
          <div role="group" aria-label="Scope" className="flex rounded-control border border-line bg-surface-1 p-0.5">
            {(["all", "mine"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={scope === s}
                onClick={() => setScope(s)}
                className={cn("h-7 rounded-[5px] px-3 text-xs font-medium transition-colors", scope === s ? "bg-surface-3 text-fg" : "text-fg-muted hover:text-fg")}
              >
                {s === "all" ? "Everyone" : "Mine"}
              </button>
            ))}
          </div>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricTile label="Open" value={Math.max(openCount, 0)} loading={stats.isLoading} hint="To do, in progress, review" />
        <MetricTile label="In progress" value={stats.data?.in_progress_tasks ?? 0} tone="info" loading={stats.isLoading} />
        <MetricTile label="Overdue" value={stats.data?.overdue_tasks ?? 0} tone={stats.data?.overdue_tasks ? "danger" : "default"} loading={stats.isLoading} href="/tasks?overdue=1" hint="View overdue tasks" />
        <MetricTile
          label="Done"
          value={stats.data?.completed_tasks ?? 0}
          tone="ok"
          loading={stats.isLoading}
          hint={stats.data && stats.data.avg_completion_days > 0 ? `Avg ${stats.data.avg_completion_days} days to finish` : undefined}
        />
      </div>

      {error ? (
        <ErrorState title="Could not load the board" error={error} onRetry={() => { void open.refetch(); void done.refetch(); }} />
      ) : loading ? (
        <div className="grid flex-1 grid-cols-1 gap-3 md:grid-cols-4" aria-busy>
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      ) : totalTasks === 0 ? (
        <EmptyState
          title={scope === "mine" ? "Nothing assigned to you" : "No tasks yet"}
          description="Create a task here, or tell ORBIT what needs doing in plain language."
          action={
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => openNewTask()}>
                <Plus className="h-3.5 w-3.5" aria-hidden /> New task
              </Button>
              <Button onClick={() => void ask("Plan my day")}>
                <Bot className="h-3.5 w-3.5" aria-hidden /> Ask ORBIT
              </Button>
            </div>
          }
        />
      ) : (
        <KanbanBoard
          tasks={tasks}
          totals={{ DONE: done.data?.meta.total }}
          onMove={(task, status) => move.mutate({ id: task.id, status })}
          onAdd={(status) => openNewTask(status)}
        />
      )}
    </div>
  );
}
