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
      <div className="w-full bg-[#111821] border border-[#263241] rounded-md overflow-hidden p-8 text-center text-slate-400 text-xs">
        <div className="inline-block w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mb-2.5"></div>
        <p>Loading tasks from ORBIT database...</p>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="w-full bg-[#111821] border border-dashed border-[#263241] rounded-md p-10 text-center text-slate-400">
        <p className="text-xs font-semibold text-slate-300 mb-1">No tasks found</p>
        <p className="text-[11px] text-slate-500">
          Try adjusting your search filters or create a new task.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full bg-[#111821] border border-[#263241] rounded-md overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-[#0C121A] border-b border-[#263241] text-[11px] font-semibold text-slate-400 uppercase tracking-wider font-mono">
            <tr>
              <th className="py-3 px-4">Task Details</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Priority</th>
              <th className="py-3 px-4">Assignee</th>
              <th className="py-3 px-4">Due Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1C2633]">
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
                  className="hover:bg-[#151F2C] transition-colors group"
                >
                  {/* Title & Description */}
                  <td className="py-3 px-4 max-w-sm">
                    <Link
                      href={`/tasks/${task.id}`}
                      className="font-semibold text-slate-100 group-hover:text-blue-400 transition-colors text-xs line-clamp-1"
                    >
                      {task.title}
                    </Link>
                    {task.description && (
                      <p className="text-slate-400 line-clamp-1 text-[11px] mt-0.5">
                        {task.description}
                      </p>
                    )}
                    {task.tags && task.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {task.tags.map((tag, i) => (
                          <span
                            key={i}
                            className="text-[10px] font-mono px-1.5 py-0.2 rounded-md bg-[#151F2C] text-slate-400 border border-[#263241]"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>

                  {/* Status */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <StatusBadge status={task.status} size="sm" />
                  </td>

                  {/* Priority */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <PriorityBadge priority={task.priority} size="sm" />
                  </td>

                  {/* Assignee */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-md bg-[#151F2C] border border-[#263241] flex items-center justify-center text-[9px] text-blue-400 font-semibold uppercase">
                        {task.assignee?.display_name?.charAt(0) || <UserIcon className="w-2.5 h-2.5" />}
                      </div>
                      <span className="text-slate-300 text-xs">
                        {task.assignee?.display_name || "Unassigned"}
                      </span>
                    </div>
                  </td>

                  {/* Due Date */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    {task.due_date ? (
                      <div
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-mono ${
                          isOverdue
                            ? "bg-rose-950/40 text-rose-300 border border-rose-500/40 font-semibold"
                            : "bg-[#151F2C] text-slate-400 border border-[#263241]"
                        }`}
                      >
                        {isOverdue ? (
                          <AlertTriangle className="w-3 h-3 text-rose-400" />
                        ) : (
                          <Calendar className="w-3 h-3 text-slate-400" />
                        )}
                        <span>{formatDate(task.due_date)}</span>
                      </div>
                    ) : (
                      <span className="text-slate-500 text-[11px] font-mono">No deadline</span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="py-3 px-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-1">
                      {task.status !== "DONE" && (
                        <button
                          onClick={() => onCompleteTask(task.id)}
                          title="Mark Done"
                          className="p-1 rounded-md text-emerald-400 hover:bg-emerald-950/40 transition-colors"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      )}

                      <Link
                        href={`/tasks/${task.id}`}
                        title="View Details"
                        className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-[#151F2C] transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </Link>

                      <button
                        onClick={() => onDeleteTask(task.id)}
                        title="Delete Task"
                        className="p-1 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
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
