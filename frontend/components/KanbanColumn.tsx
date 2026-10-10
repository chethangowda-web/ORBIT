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
    <div className="flex flex-col flex-1 min-w-[280px] bg-[#0C121A] border border-[#263241] rounded-md p-3">
      {/* Column Header */}
      <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-[#1C2633]">
        <div className="flex items-center gap-2">
          <StatusBadge status={status} size="sm" />
          <span className="text-[11px] font-mono font-bold text-slate-300 px-2 py-0.5 rounded-md bg-[#151F2C] border border-[#263241]">
            {tasks.length}
          </span>
        </div>

        {onAddTask && (
          <button
            onClick={() => onAddTask(status)}
            title="Add task to column"
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-[#151F2C] border border-transparent hover:border-[#263241] transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Task Cards Container */}
      <div className="flex-1 space-y-2 overflow-y-auto max-h-[calc(100vh-250px)] pr-1 custom-scrollbar">
        {tasks.length === 0 ? (
          <div className="h-28 flex flex-col items-center justify-center border border-dashed border-[#263241] rounded-md text-slate-500 text-xs">
            <span>No tasks in lane</span>
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
