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
    <div className="bg-[#151F2C] border border-[#263241] hover:border-slate-600 rounded-md p-3.5 transition-colors group relative">
      {/* Header: Priority & Due Date */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <PriorityBadge priority={task.priority} size="sm" />
        {task.due_date && (
          <div
            className={`flex items-center gap-1.5 text-[11px] font-mono px-2 py-0.5 rounded-md border ${
              isOverdue
                ? "bg-rose-950/40 text-rose-300 border-rose-500/40 font-semibold"
                : "bg-[#111821] text-slate-400 border-[#263241]"
            }`}
          >
            {isOverdue ? (
              <AlertTriangle className="w-3 h-3 text-rose-400" />
            ) : (
              <Calendar className="w-3 h-3 text-slate-400" />
            )}
            <span>{formatDate(task.due_date)}</span>
          </div>
        )}
      </div>

      {/* Title */}
      <Link href={`/tasks/${task.id}`}>
        <h3 className="text-xs font-semibold text-[#E5EAF1] group-hover:text-blue-400 transition-colors line-clamp-2 mb-1.5 leading-snug">
          {task.title}
        </h3>
      </Link>

      {/* Description Snippet */}
      {task.description && (
        <p className="text-[11px] text-slate-400 line-clamp-2 mb-2.5 leading-relaxed">
          {task.description}
        </p>
      )}

      {/* Tags */}
      {task.tags && task.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2.5">
          {task.tags.slice(0, 3).map((tag, idx) => (
            <span
              key={idx}
              className="text-[10px] font-mono px-1.5 py-0.5 rounded-md bg-[#111821] text-slate-300 border border-[#263241]"
            >
              #{tag}
            </span>
          ))}
          {task.tags.length > 3 && (
            <span className="text-[10px] font-mono text-slate-500 self-center">
              +{task.tags.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Footer: Assignee & Action */}
      <div className="flex items-center justify-between pt-2 border-t border-[#263241] mt-1">
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <div className="w-5 h-5 rounded-md bg-[#111821] border border-[#263241] flex items-center justify-center text-[10px] text-blue-400 font-semibold uppercase">
            {task.assignee?.display_name?.charAt(0) || <User className="w-2.5 h-2.5" />}
          </div>
          <span className="truncate max-w-[100px] text-[11px] text-slate-300">
            {task.assignee?.display_name || "Unassigned"}
          </span>
        </div>

        {nextStatus && onStatusChange && (
          <button
            onClick={() => onStatusChange(task.id, nextStatus)}
            title={`Move to ${nextStatus}`}
            className="flex items-center gap-1 text-[11px] font-medium text-slate-300 hover:text-white bg-[#111821] hover:bg-[#1A2636] border border-[#263241] hover:border-blue-500/40 px-2 py-0.5 rounded-md transition-colors font-mono"
          >
            <span>Advance</span>
            <ChevronRight className="w-3 h-3" />
          </button>
        )}

        {task.status === "DONE" && (
          <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Complete</span>
          </span>
        )}
      </div>
    </div>
  );
};
