"use client";

import React, { createContext, useCallback, useContext, useMemo, useState } from "react";
import { TaskFormModal } from "@/components/tasks/TaskFormModal";
import type { Task, TaskStatus } from "@/types";

interface ShellContextValue {
  openNewTask: (status?: TaskStatus) => void;
  openEditTask: (task: Task) => void;
}

const ShellContext = createContext<ShellContextValue | undefined>(undefined);

/** Owns the task form dialog so any screen, the top bar and the palette can open it. */
export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [task, setTask] = useState<Task | null>(null);
  const [status, setStatus] = useState<TaskStatus>("TODO");

  const openNewTask = useCallback((next: TaskStatus = "TODO") => {
    setTask(null);
    setStatus(next);
    setOpen(true);
  }, []);
  const openEditTask = useCallback((t: Task) => {
    setTask(t);
    setOpen(true);
  }, []);

  const value = useMemo(() => ({ openNewTask, openEditTask }), [openNewTask, openEditTask]);
  return (
    <ShellContext.Provider value={value}>
      {children}
      <TaskFormModal open={open} onClose={() => setOpen(false)} task={task} defaultStatus={status} />
    </ShellContext.Provider>
  );
}

export function useShell(): ShellContextValue {
  const ctx = useContext(ShellContext);
  if (!ctx) throw new Error("useShell must be used within ShellProvider");
  return ctx;
}
