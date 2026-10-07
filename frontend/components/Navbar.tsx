"use client";

import React from "react";
import { Plus } from "lucide-react";

interface NavbarProps {
  title?: string;
  onCreateTask?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ title = "Dashboard", onCreateTask }) => {
  return (
    <header className="h-16 px-6 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-md flex items-center justify-between sticky top-0 z-30">
      <div>
        <h1 className="text-lg font-bold text-white tracking-tight">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        {/* Status pill */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/30 border border-emerald-500/20 text-emerald-400 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-medium">ORBIT Engine Live</span>
        </div>

        {/* Create Task Button */}
        {onCreateTask && (
          <button
            onClick={onCreateTask}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Task</span>
          </button>
        )}
      </div>
    </header>
  );
};
