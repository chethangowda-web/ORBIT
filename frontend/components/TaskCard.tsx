"use client";

import React from "react";
import Link from "next/link";
import { Task, TaskStatus } from "@/types";
import { PriorityBadge } from "./PriorityBadge";
import { Calendar, User, CheckCircle2, ChevronRight, AlertTriangle } from "lucide-react";

interface TaskCardProps {
  task: Task;
  onStatusChange?: (taskId: string, newStatus: TaskStatus) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({ task, onStatusChange }) => {
  const isOverdue =
    task.due_date &&
    task.status !== "DONE" &&
    new Date(task.due_date + "T23:59:59").getTime() < Date.now();

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  };

  const nextStatusMap: Record<TaskStatus, TaskStatus | null> = {
    TODO: "IN_PROGRESS",
    IN_PROGRESS: "REVIEW",
    REVIEW: "DONE",
    DONE: null,
  };

  const nextStatus = nextStatusMap[task.status];

  return (
    <div className="glass-card rounded-xl p-4 transition-all duration-200 group relative">
      {/* Header: Priority & Due Date */}
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <PriorityBadge priority={task.priority} size="sm" />
        {task.due_date && (
          <div
            className={`flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded ${
              isOverdue
                ? "bg-rose-950/70 text-rose-300 border border-rose-500/30"
                : "bg-slate-800/60 text-slate-400"
            }`}
          >
            {isOverdue ? (
              <AlertTriangle className="w-3 h-3 text-rose-400" />
            ) : (
              <Calendar className="w-3 h-3 text-slate-400" />
            )}
            <span>{task.due_date ? formatDate(task.due_date) : ""}</span>
          </div>
        )}
      </div>

      {/* Title */}
      <Link href={`/tasks/${task.id}`}>
        <h3 className="text-sm font-semibold text-slate-100 hover:text-indigo-400 transition-colors line-clamp-2 mb-2 leading-snug">
          {task.title}
        </h3>
      </Link>

      {/* Description Snippet */}
      {task.description && (
        <p className="text-xs text-slate-400 line-clamp-2 mb-3 leading-relaxed">
          {task.description}
        </p>
      )}

      {/* Tags */}
      {task.tags && task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {task.tags.slice(0, 3).map((tag, idx) => (
            <span
              key={idx}
              className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-slate-300 border border-slate-700/50"
            >
              #{tag}
            </span>
          ))}
          {task.tags.length > 3 && (
            <span className="text-[10px] text-slate-500 self-center">
              +{task.tags.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Footer: Assignee & Action */}
      <div className="flex items-center justify-between pt-2.5 border-t border-slate-800/80 mt-1">
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <div className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-slate-300 font-semibold uppercase">
            {task.assignee?.display_name?.charAt(0) || <User className="w-2.5 h-2.5" />}
          </div>
          <span className="truncate max-w-[100px] text-[11px]">
            {task.assignee?.display_name || "Unassigned"}
          </span>
        </div>

        {nextStatus && onStatusChange && (
          <button
            onClick={() => onStatusChange(task.id, nextStatus)}
            title={`Move to ${nextStatus}`}
            className="flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-indigo-300 hover:bg-indigo-950/40 px-2 py-1 rounded transition-colors"
          >
            <span>Advance</span>
            <ChevronRight className="w-3 h-3" />
          </button>
        )}

        {task.status === "DONE" && (
          <span className="flex items-center gap-1 text-[11px] text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Complete</span>
          </span>
        )}
      </div>
    </div>
  );
};
