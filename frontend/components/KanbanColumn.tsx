"use client";

import React from "react";
import { Task, TaskStatus } from "@/types";
import { TaskCard } from "./TaskCard";
import { StatusBadge } from "./StatusBadge";
import { Plus } from "lucide-react";

interface KanbanColumnProps {
  status: TaskStatus;
  tasks: Task[];
  onStatusChange?: (taskId: string, newStatus: TaskStatus) => void;
  onAddTask?: (status: TaskStatus) => void;
}

export const KanbanColumn: React.FC<KanbanColumnProps> = ({
  status,
  tasks,
  onStatusChange,
  onAddTask,
}) => {
  return (
    <div className="flex flex-col flex-1 min-w-[280px] bg-slate-900/40 border border-slate-800/80 rounded-2xl p-3.5 backdrop-blur-sm">
      {/* Column Header */}
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <StatusBadge status={status} size="sm" />
          <span className="text-xs font-bold text-slate-400 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700/50">
            {tasks.length}
          </span>
        </div>

        {onAddTask && (
          <button
            onClick={() => onAddTask(status)}
            title="Add task to column"
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <Plus className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Task Cards Container */}
      <div className="flex-1 space-y-3 overflow-y-auto max-h-[calc(100vh-250px)] pr-1">
        {tasks.length === 0 ? (
          <div className="h-32 flex flex-col items-center justify-center border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs">
            <span>No tasks in this lane</span>
          </div>
        ) : (
          tasks.map((task) => (
            <TaskCard key={task.id} task={task} onStatusChange={onStatusChange} />
          ))
        )}
      </div>
    </div>
  );
};
