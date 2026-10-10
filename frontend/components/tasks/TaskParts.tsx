import React from "react";
import { AlertTriangle, Calendar } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatDue, isOverdue } from "@/lib/format";
import type { Task } from "@/types";

/** Due date chip: red and labelled "Nd overdue" when late, otherwise relative text. */
export function DueChip({ task, className }: { task: Pick<Task, "due_date" | "status">; className?: string }) {
  if (!task.due_date) return <span className={cn("text-[11px] text-fg-faint", className)}>No due date</span>;
  const overdue = isOverdue(task);
  return (
    <span
      className={cn(
        "num inline-flex h-5 items-center gap-1 rounded-control border px-1.5 text-[11px]",
        overdue ? "border-danger/40 bg-danger/10 font-semibold text-danger" : "border-line bg-surface-2 text-fg-muted",
        className,
      )}
      title={task.due_date}
    >
      {overdue ? <AlertTriangle className="h-3 w-3" aria-hidden /> : <Calendar className="h-3 w-3" aria-hidden />}
      {formatDue(task.due_date)}
    </span>
  );
}

export function TagList({ tags, max = 3 }: { tags?: string[]; max?: number }) {
  if (!tags || tags.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {tags.slice(0, max).map((tag) => (
        <span key={tag} className="num rounded-control border border-line bg-surface-2 px-1.5 text-[10px] text-fg-muted">
          #{tag}
        </span>
      ))}
      {tags.length > max && <span className="num text-[10px] text-fg-faint">+{tags.length - max}</span>}
    </div>
  );
}
