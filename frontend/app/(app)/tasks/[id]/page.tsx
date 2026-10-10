"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Activity, ArrowLeft, Calendar, CheckCircle2, Clock, Pencil, Tag, Trash2, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { ConfirmDialog } from "@/components/ui/Overlay";
import { Avatar, EmptyState, ErrorState, Panel, PanelHeader, Skeleton } from "@/components/ui/Primitives";
import { useShell } from "@/components/shell/ShellContext";
import { Attachments } from "@/components/tasks/Attachments";
import { Comments } from "@/components/tasks/Comments";
import { DueChip } from "@/components/tasks/TaskParts";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { describeAudit, formatDate, formatDateTime, sourceLabel, timeAgo } from "@/lib/format";
import { useCompleteTask, useDeleteTask, useTask, useTaskHistory } from "@/lib/hooks";

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="section-label mb-1">{label}</dt>
      <dd className="text-[13px] text-fg">{children}</dd>
    </div>
  );
}

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { isManager } = useAuth();
  const { openEditTask } = useShell();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: task, isLoading, error, refetch } = useTask(id);
  const { data: history = [], isLoading: historyLoading } = useTaskHistory(id);
  const complete = useCompleteTask();
  const remove = useDeleteTask(() => router.replace("/tasks"));

  const back = (
    <Link href="/tasks" className="mb-4 inline-flex items-center gap-1.5 text-xs text-fg-muted transition-colors hover:text-fg">
      <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> All tasks
    </Link>
  );

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl">
        {back}
        <Skeleton className="mb-3 h-8 w-2/3" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error || !task) {
    const notFound = error instanceof ApiError && (error.status === 404 || error.status === 403);
    return (
      <div className="mx-auto max-w-4xl">
        {back}
        {notFound ? (
          <EmptyState title="Task not found" description="It may have been deleted, or you may not have access to it." action={<Button onClick={() => router.push("/tasks")}>Back to tasks</Button>} />
        ) : (
          <ErrorState title="Could not load this task" error={error} onRetry={() => void refetch()} />
        )}
      </div>
    );
  }

  const closed = task.status === "DONE" || task.status === "CANCELLED";

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      {back}

      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line-subtle p-5">
          <div className="min-w-0 space-y-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={task.status} />
              <PriorityBadge priority={task.priority} />
              <DueChip task={task} />
            </div>
            <h1 className="text-xl font-semibold leading-snug text-fg">{task.title}</h1>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {!closed && (
              <Button variant="primary" loading={complete.isPending} onClick={() => complete.mutate(task.id)}>
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden /> Mark done
              </Button>
            )}
            <Button onClick={() => openEditTask(task)}>
              <Pencil className="h-3.5 w-3.5" aria-hidden /> Edit
            </Button>
            {isManager && (
              <Button variant="danger" onClick={() => setConfirmDelete(true)}>
                <Trash2 className="h-3.5 w-3.5" aria-hidden /> Delete
              </Button>
            )}
          </div>
        </div>

        <div className="space-y-5 p-5">
          <div>
            <h2 className="section-label mb-1.5">Description</h2>
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-fg-muted">{task.description || "No description."}</p>
          </div>

          <dl className="grid grid-cols-2 gap-4 border-t border-line-subtle pt-5 md:grid-cols-4">
            <Meta label="Assignee">
              <span className="flex items-center gap-2">
                {task.assignee ? <Avatar name={task.assignee.display_name} size="sm" /> : <UserIcon className="h-3.5 w-3.5 text-fg-faint" aria-hidden />}
                {task.assignee?.display_name ?? "Unassigned"}
              </span>
            </Meta>
            <Meta label="Due">
              <span className="flex items-center gap-1.5">
                <Calendar className="h-3.5 w-3.5 text-fg-faint" aria-hidden />
                {task.due_date ? formatDate(task.due_date) : "No due date"}
              </span>
            </Meta>
            <Meta label="Created">
              <span className="flex items-center gap-1.5 text-fg-muted">
                <Clock className="h-3.5 w-3.5 text-fg-faint" aria-hidden />
                {formatDate(task.created_at)}
              </span>
            </Meta>
            <Meta label="Created by">{task.creator?.display_name ?? "System"}</Meta>
          </dl>

          {task.tags && task.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 border-t border-line-subtle pt-4">
              <Tag className="h-3.5 w-3.5 text-fg-faint" aria-hidden />
              {task.tags.map((tag) => (
                <span key={tag} className="num rounded-control border border-line bg-surface-2 px-2 py-0.5 text-[11px] text-fg-muted">
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </Panel>

      <Attachments taskId={task.id} canEdit />

      <Comments taskId={task.id} />

      <Panel>
        <PanelHeader title="Activity" description="Every change is recorded with who made it and where." icon={<Activity className="h-4 w-4" />} />
        <div className="p-5">
          {historyLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : history.length === 0 ? (
            <p className="text-xs text-fg-muted">No activity recorded yet.</p>
          ) : (
            <ol className="relative space-y-4 border-l border-line pl-5">
              {history.map((entry) => (
                <li key={entry.id} className="relative">
                  <span className="absolute -left-[25px] top-1.5 h-2 w-2 rounded-full border-2 border-surface-1 bg-accent" aria-hidden />
                  <p className="text-[13px] text-fg">{describeAudit(entry)}</p>
                  <p className="mt-0.5 text-[11px] text-fg-faint">
                    <time dateTime={entry.created_at} title={formatDateTime(entry.created_at)}>
                      {timeAgo(entry.created_at)}
                    </time>
                    {" via "}
                    {sourceLabel(entry.source)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </Panel>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this task?"
        description={`"${task.title}" will be removed from the board and lists.`}
        confirmLabel="Delete task"
        loading={remove.isPending}
        onClose={() => setConfirmDelete(false)}
        onConfirm={() => remove.mutate(task.id)}
      />
    </div>
  );
}
