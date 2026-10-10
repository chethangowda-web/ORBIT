"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle, Plus, RotateCcw, Search, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { CompactSelect } from "@/components/ui/Field";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, PageHeader } from "@/components/ui/Primitives";
import { useShell } from "@/components/shell/ShellContext";
import { TaskTable } from "@/components/tasks/TaskTable";
import { useAuth } from "@/lib/auth";
import { ALL_STATUSES, PRIORITIES, PRIORITY_LABEL, STATUS_LABEL } from "@/lib/constants";
import { cn } from "@/lib/cn";
import { useCompleteTask, useDeleteTask, useTasks, useUsers } from "@/lib/hooks";
import { hasActiveFilters, nextSort, parseView, serializeView, toApiFilters, type TaskView } from "@/lib/task-query";
import type { Task } from "@/types";

const PAGE_SIZE = 15;

function TasksScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { user, isManager } = useAuth();
  const { openNewTask, openEditTask } = useShell();
  const { data: users = [] } = useUsers();

  const view = useMemo(() => parseView(new URLSearchParams(params.toString())), [params]);
  const [search, setSearch] = useState(view.q);
  const [toDelete, setToDelete] = useState<Task | null>(null);

  const update = useCallback(
    (patch: Partial<TaskView>) => {
      const next = { ...view, page: 1, ...patch };
      const query = serializeView(next);
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [view, router, pathname],
  );

  // Debounce typing into the URL-backed search term.
  useEffect(() => {
    if (search === view.q) return;
    const id = window.setTimeout(() => update({ q: search }), 300);
    return () => window.clearTimeout(id);
  }, [search, view.q, update]);
  useEffect(() => setSearch(view.q), [view.q]);

  const filters = useMemo(() => toApiFilters(view, user?.id, PAGE_SIZE), [view, user?.id]);
  const { data, isLoading, isFetching, error, refetch } = useTasks(filters, { poll: true });
  const complete = useCompleteTask();
  const remove = useDeleteTask(() => setToDelete(null));

  const active = hasActiveFilters(view);
  const reset = () => {
    setSearch("");
    router.replace(pathname, { scroll: false });
  };

  const assigneeOptions = [
    { value: "", label: "Anyone" },
    { value: "me", label: "Me" },
    ...users.filter((u) => u.id !== user?.id).map((u) => ({ value: u.id, label: u.display_name })),
  ];

  return (
    <div>
      <PageHeader
        title="Tasks"
        description={isManager ? "Every task across the team." : "Tasks you created or are assigned."}
        actions={
          <Button variant="primary" onClick={() => openNewTask()}>
            <Plus className="h-3.5 w-3.5" aria-hidden /> New task
          </Button>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2 rounded-panel border border-line bg-surface-1 p-2.5">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-faint" aria-hidden />
          <input
            type="search"
            aria-label="Search tasks"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, description or tag"
            className="h-8 w-full rounded-control border border-line bg-surface-2 pl-8 pr-8 text-[13px] text-fg placeholder:text-fg-faint focus:border-accent focus:outline-none [&::-webkit-search-cancel-button]:hidden"
          />
          {search && (
            <button type="button" aria-label="Clear search" onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-fg-faint hover:text-fg">
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <CompactSelect label="Status" value={view.status} onChange={(v) => update({ status: v as TaskView["status"] })} options={[{ value: "", label: "Any status" }, ...ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))]} />
        <CompactSelect label="Priority" value={view.priority} onChange={(v) => update({ priority: v as TaskView["priority"] })} options={[{ value: "", label: "Any priority" }, ...PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))]} />
        <CompactSelect label="Assignee" value={view.assignee} onChange={(v) => update({ assignee: v })} options={assigneeOptions} />
        <button
          type="button"
          aria-pressed={view.overdue}
          onClick={() => update({ overdue: !view.overdue })}
          className={cn("inline-flex h-8 items-center gap-1.5 rounded-control border px-2.5 text-xs font-medium transition-colors", view.overdue ? "border-danger/40 bg-danger/10 text-danger" : "border-line bg-surface-2 text-fg-muted hover:text-fg")}
        >
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> Overdue
        </button>
        {active && (
          <Button size="sm" variant="ghost" onClick={reset}>
            <RotateCcw className="h-3 w-3" aria-hidden /> Reset
          </Button>
        )}
      </div>

      {error ? (
        <ErrorState title="Could not load tasks" error={error} onRetry={() => void refetch()} />
      ) : !isLoading && data && data.items.length === 0 ? (
        <EmptyState
          title={active ? "No tasks match these filters" : "No tasks yet"}
          description={active ? "Try a broader search or clear the filters." : "Create the first task to get started."}
          action={active ? <Button onClick={reset}>Clear filters</Button> : <Button variant="primary" onClick={() => openNewTask()}>New task</Button>}
        />
      ) : (
        <div className={cn("transition-opacity", isFetching && !isLoading && "opacity-70")}>
          <TaskTable
            tasks={data?.items ?? []}
            loading={isLoading}
            sortBy={view.sortBy}
            sortDir={view.sortDir}
            onSort={(column) => update({ ...nextSort(view, column), page: 1 })}
            onComplete={(task) => complete.mutate(task.id)}
            onEdit={openEditTask}
            onDelete={isManager ? setToDelete : undefined}
          />
          {data && <Pagination meta={data.meta} noun="tasks" onPageChange={(page) => update({ page })} />}
        </div>
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title="Delete this task?"
        description={toDelete ? `"${toDelete.title}" will be removed from the board and lists.` : ""}
        confirmLabel="Delete task"
        loading={remove.isPending}
        onClose={() => setToDelete(null)}
        onConfirm={() => toDelete && remove.mutate(toDelete.id)}
      />
    </div>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={null}>
      <TasksScreen />
    </Suspense>
  );
}
