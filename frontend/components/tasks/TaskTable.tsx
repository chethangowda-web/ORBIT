"use client";

import React from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, Check, Pencil, Trash2 } from "lucide-react";
import { Avatar, Skeleton } from "@/components/ui/Primitives";
import { IconButton } from "@/components/ui/Button";
import { PriorityBadge, StatusBadge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { DueChip, TagList } from "./TaskParts";
import type { Task, TaskFilters } from "@/types";

type SortKey = NonNullable<TaskFilters["sort_by"]>;

interface Props {
  tasks: Task[];
  loading?: boolean;
  sortBy: SortKey;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
  onComplete: (task: Task) => void;
  onEdit: (task: Task) => void;
  /** Omit to hide the delete action (employees cannot delete). */
  onDelete?: (task: Task) => void;
}

function SortHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
  className,
}: {
  label: string;
  column: SortKey;
  sortBy: SortKey;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const active = sortBy === column;
  const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th
      scope="col"
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
      className={cn("px-3 py-2 text-left", className)}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        className={cn("inline-flex items-center gap-1 transition-colors hover:text-fg", active && "text-fg")}
      >
        {label}
        <Icon className={cn("h-3 w-3", !active && "opacity-50")} aria-hidden />
      </button>
    </th>
  );
}

export function TaskTable({ tasks, loading, sortBy, sortDir, onSort, onComplete, onEdit, onDelete }: Props) {
  const sortProps = { sortBy, sortDir, onSort };
  return (
    <div className="overflow-x-auto rounded-panel border border-line bg-surface-1">
      <table className="w-full min-w-[820px] text-left text-[12.5px]">
        <thead className="border-b border-line bg-surface-2/50 text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-faint">
          <tr>
            <SortHeader label="Task" column="title" {...sortProps} />
            <SortHeader label="Status" column="status" {...sortProps} />
            <SortHeader label="Priority" column="priority" {...sortProps} />
            <th scope="col" className="px-3 py-2">
              Assignee
            </th>
            <SortHeader label="Due" column="due_date" {...sortProps} />
            <th scope="col" className="px-3 py-2 text-right">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line-subtle">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 6 }).map((__, j) => (
                    <td key={j} className="px-3 py-3">
                      <Skeleton className="h-4 w-full max-w-[140px]" />
                    </td>
                  ))}
                </tr>
              ))
            : tasks.map((task) => (
                <tr key={task.id} className="group transition-colors hover:bg-surface-2/60">
                  <td className="max-w-[360px] px-3 py-2.5">
                    <Link href={`/tasks/${task.id}`} className="line-clamp-1 font-medium text-fg hover:text-accent">
                      {task.title}
                    </Link>
                    <div className="mt-0.5">
                      <TagList tags={task.tags} max={3} />
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <StatusBadge status={task.status} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <PriorityBadge priority={task.priority} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <span className="flex items-center gap-2 text-fg-muted">
                      <Avatar name={task.assignee?.display_name} size="sm" />
                      {task.assignee?.display_name ?? "Unassigned"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <DueChip task={task} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <div className="flex items-center justify-end gap-0.5">
                      {task.status !== "DONE" && task.status !== "CANCELLED" && (
                        <IconButton label={`Mark "${task.title}" done`} size="sm" tone="ok" onClick={() => onComplete(task)}>
                          <Check className="h-3.5 w-3.5" />
                        </IconButton>
                      )}
                      <IconButton label={`Edit "${task.title}"`} size="sm" onClick={() => onEdit(task)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </IconButton>
                      {onDelete && (
                        <IconButton label={`Delete "${task.title}"`} size="sm" tone="danger" onClick={() => onDelete(task)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </IconButton>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  );
}
