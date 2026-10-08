"use client";

import React from "react";
import Link from "next/link";
import { Task } from "@/types";
import { StatusBadge } from "./StatusBadge";
import { PriorityBadge } from "./PriorityBadge";
import { Check, Trash2, Eye, Calendar, User as UserIcon, AlertTriangle } from "lucide-react";

interface TaskTableProps {
  tasks: Task[];
  isLoading: boolean;
  onCompleteTask: (id: string) => void;
  onDeleteTask: (id: string) => void;
}

export const TaskTable: React.FC<TaskTableProps> = ({
  tasks,
  isLoading,
  onCompleteTask,
  onDeleteTask,
}) => {
  if (isLoading) {
    return (
      <div className="w-full bg-slate-900/40 border border-slate-800 rounded-2xl overflow-hidden p-8 text-center text-slate-400 text-sm">
        <div className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mb-3"></div>
        <p>Loading tasks from ORBIT database...</p>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="w-full bg-slate-900/40 border border-dashed border-slate-800 rounded-2xl p-12 text-center text-slate-400">
        <p className="text-sm font-medium text-slate-300 mb-1">No tasks found</p>
        <p className="text-xs text-slate-500">
          Try adjusting your search filters or create a new task.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full bg-slate-900/50 border border-slate-800/80 rounded-2xl overflow-hidden shadow-xl backdrop-blur-md">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/70 border-b border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            <tr>
              <th className="py-3.5 px-4">Task Details</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-4">Priority</th>
              <th className="py-3.5 px-4">Assignee</th>
              <th className="py-3.5 px-4">Due Date</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {tasks.map((task) => {
              const isOverdue =
                task.due_date &&
                task.status !== "DONE" &&
                new Date(task.due_date + "T23:59:59").getTime() < Date.now();

              const formatDate = (dateStr: string) =>
                new Date(dateStr + "T00:00:00").toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                });

              return (
                <tr
                  key={task.id}
                  className="hover:bg-slate-800/40 transition-colors group"
                >
                  {/* Title & Description */}
                  <td className="py-3.5 px-4 max-w-sm">
                    <Link
                      href={`/tasks/${task.id}`}
                      className="font-semibold text-slate-100 group-hover:text-indigo-400 transition-colors text-sm line-clamp-1"
                    >
                      {task.title}
                    </Link>
                    {task.description && (
                      <p className="text-slate-400 line-clamp-1 text-[11px] mt-0.5">
                        {task.description}
                      </p>
                    )}
                    {task.tags && task.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {task.tags.map((tag, i) => (
                          <span
                            key={i}
                            className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-400"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>

                  {/* Status */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <StatusBadge status={task.status} size="sm" />
                  </td>

                  {/* Priority */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <PriorityBadge priority={task.priority} size="sm" />
                  </td>

                  {/* Assignee */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-slate-300 font-semibold uppercase">
                        {task.assignee?.display_name?.charAt(0) || <UserIcon className="w-2.5 h-2.5" />}
                      </div>
                      <span className="text-slate-300">
                        {task.assignee?.display_name || "Unassigned"}
                      </span>
                    </div>
                  </td>

                  {/* Due Date */}
                  <td className="py-3.5 px-4 whitespace-nowrap">
                    {task.due_date ? (
                      <div
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium ${
                          isOverdue
                            ? "bg-rose-950/70 text-rose-300 border border-rose-500/30"
                            : "text-slate-400"
                        }`}
                      >
                        {isOverdue ? (
                          <AlertTriangle className="w-3 h-3 text-rose-400" />
                        ) : (
                          <Calendar className="w-3 h-3 text-slate-500" />
                        )}
                        <span>{formatDate(task.due_date)}</span>
                      </div>
                    ) : (
                      <span className="text-slate-500 text-[11px]">No deadline</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3.5 px-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1.5">
                      {task.status !== "DONE" && (
                        <button
                          onClick={() => onCompleteTask(task.id)}
                          title="Mark Done"
                          className="p-1.5 rounded-lg text-emerald-400 hover:bg-emerald-950/40 transition-colors"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                      )}

                      <Link
                        href={`/tasks/${task.id}`}
                        title="View Details"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        <Eye className="w-4 h-4" />
                      </Link>

                      <button
                        onClick={() => onDeleteTask(task.id)}
                        title="Delete Task"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
