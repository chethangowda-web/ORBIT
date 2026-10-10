"use client";

import React from "react";
import { Filter, RotateCcw } from "lucide-react";
import { User } from "@/types";

interface FilterBarProps {
  status: string;
  onStatusChange: (status: string) => void;
  priority: string;
  onPriorityChange: (priority: string) => void;
  assigneeId: string;
  onAssigneeChange: (assigneeId: string) => void;
  users: User[];
  onReset: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({
  status,
  onStatusChange,
  priority,
  onPriorityChange,
  assigneeId,
  onAssigneeChange,
  users,
  onReset,
}) => {
  const hasActiveFilters = Boolean(status || priority || assigneeId);

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      <div className="flex items-center gap-1.5 text-xs text-slate-400 font-medium mr-1">
        <Filter className="w-3.5 h-3.5 text-blue-400" />
        <span>Filters:</span>
      </div>

      {/* Status filter */}
      <select
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className="px-2.5 py-1.5 rounded-md bg-[#111821] border border-[#263241] text-[#E5EAF1] text-xs focus:outline-none focus:border-blue-500 transition-colors"
      >
        <option value="">All Statuses</option>
        <option value="TODO">To Do</option>
        <option value="IN_PROGRESS">In Progress</option>
        <option value="REVIEW">Review</option>
        <option value="DONE">Done</option>
      </select>

      {/* Priority filter */}
      <select
        value={priority}
        onChange={(e) => onPriorityChange(e.target.value)}
        className="px-2.5 py-1.5 rounded-md bg-[#111821] border border-[#263241] text-[#E5EAF1] text-xs focus:outline-none focus:border-blue-500 transition-colors"
      >
        <option value="">All Priorities</option>
        <option value="LOW">Low</option>
        <option value="MEDIUM">Medium</option>
        <option value="HIGH">High</option>
        <option value="CRITICAL">Critical</option>
      </select>

      {/* Assignee filter */}
      <select
        value={assigneeId}
        onChange={(e) => onAssigneeChange(e.target.value)}
        className="px-2.5 py-1.5 rounded-md bg-[#111821] border border-[#263241] text-[#E5EAF1] text-xs focus:outline-none focus:border-blue-500 transition-colors"
      >
        <option value="">All Assignees</option>
        {users.map((u) => (
          <option key={u.id} value={u.id}>
            {u.display_name}
          </option>
        ))}
      </select>

      {/* Reset button */}
      {hasActiveFilters && (
        <button
          onClick={onReset}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-[#151F2C] hover:bg-[#1A2636] border border-[#263241] hover:border-slate-600 text-slate-300 text-xs transition-colors font-mono"
        >
          <RotateCcw className="w-3 h-3" />
          <span>Reset</span>
        </button>
      )}
    </div>
  );
};
