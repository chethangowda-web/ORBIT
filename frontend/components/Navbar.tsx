"use client";

import React from "react";
import { Plus } from "lucide-react";

interface NavbarProps {
  title?: string;
  onCreateTask?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ title = "Dashboard", onCreateTask }) => {
  return (
    <header className="h-14 px-6 border-b border-[#263241] bg-[#0C121A] flex items-center justify-between sticky top-0 z-30">
      <div>
        <h1 className="text-sm font-semibold text-slate-100 tracking-tight">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Status pill */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-950/30 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>ORBIT Engine Live</span>
        </div>

        {/* Create Task Button */}
        {onCreateTask && (
          <button
            onClick={onCreateTask}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Task</span>
          </button>
        )}
      </div>
    </header>
  );
};
