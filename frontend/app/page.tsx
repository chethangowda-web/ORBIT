"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Task, TaskStatus } from "@/types";
import { Navbar } from "@/components/Navbar";
import { KanbanColumn } from "@/components/KanbanColumn";
import { CreateTaskModal } from "@/components/CreateTaskModal";
import {
  CheckCircle2,
  Clock,
  Layers,
  AlertTriangle,
} from "lucide-react";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [defaultColumnStatus, setDefaultColumnStatus] = useState<TaskStatus>("TODO");

  // Fetch all tasks for Kanban
  const { data: tasksData, isLoading } = useQuery({
    queryKey: ["tasks", "kanban"],
    queryFn: () => api.tasks.list({ page_size: 100 }),
  });

  // Fetch metrics stats
  const { data: stats } = useQuery({
    queryKey: ["taskStats"],
    queryFn: () => api.analytics.stats(),
  });

  // Advance task status mutation
  const updateStatusMutation = useMutation({
    mutationFn: ({ taskId, newStatus }: { taskId: string; newStatus: TaskStatus }) =>
      api.tasks.update(taskId, { status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      queryClient.invalidateQueries({ queryKey: ["taskStats"] });
    },
  });

  const tasks: Task[] = tasksData?.tasks || [];

  const handleStatusChange = (taskId: string, newStatus: TaskStatus) => {
    updateStatusMutation.mutate({ taskId, newStatus });
  };

  const handleAddInColumn = (status: TaskStatus) => {
    setDefaultColumnStatus(status);
    setIsModalOpen(true);
  };

  // Group by status
  const todoTasks = tasks.filter((t) => t.status === "TODO");
  const inProgressTasks = tasks.filter((t) => t.status === "IN_PROGRESS");
  const reviewTasks = tasks.filter((t) => t.status === "REVIEW");
  const doneTasks = tasks.filter((t) => t.status === "DONE");

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar
        title="Dashboard & Kanban"
        onCreateTask={() => {
          setDefaultColumnStatus("TODO");
          setIsModalOpen(true);
        }}
      />

      <div className="p-6 space-y-6 flex-1 flex flex-col">
        {/* Top Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Total */}
          <div className="glass-panel rounded-2xl p-4.5 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400">Total Active Tasks</p>
              <h3 className="text-2xl font-bold text-white mt-1">
                {stats?.total_tasks ?? tasks.length}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Layers className="w-5 h-5" />
            </div>
          </div>

          {/* Card 2: In Progress */}
          <div className="glass-panel rounded-2xl p-4.5 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400">In Progress</p>
              <h3 className="text-2xl font-bold text-sky-400 mt-1">
                {stats?.in_progress_tasks ?? inProgressTasks.length}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <Clock className="w-5 h-5" />
            </div>
          </div>

          {/* Card 3: Completed */}
          <div className="glass-panel rounded-2xl p-4.5 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400">Completed</p>
              <h3 className="text-2xl font-bold text-emerald-400 mt-1">
                {stats?.completed_tasks ?? doneTasks.length}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>

          {/* Card 4: Overdue */}
          <div className="glass-panel rounded-2xl p-4.5 border border-slate-800/80 flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-slate-400">Overdue Tasks</p>
              <h3 className="text-2xl font-bold text-rose-400 mt-1">
                {stats?.overdue_tasks ?? 0}
              </h3>
            </div>
            <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Kanban Board Container */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
            <div className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-3"></div>
            Loading board...
          </div>
        ) : (
          <div className="flex-1 flex gap-4 overflow-x-auto pb-4">
            <KanbanColumn
              status="TODO"
              tasks={todoTasks}
              onStatusChange={handleStatusChange}
              onAddTask={handleAddInColumn}
            />
            <KanbanColumn
              status="IN_PROGRESS"
              tasks={inProgressTasks}
              onStatusChange={handleStatusChange}
              onAddTask={handleAddInColumn}
            />
            <KanbanColumn
              status="REVIEW"
              tasks={reviewTasks}
              onStatusChange={handleStatusChange}
              onAddTask={handleAddInColumn}
            />
            <KanbanColumn
              status="DONE"
              tasks={doneTasks}
              onStatusChange={handleStatusChange}
              onAddTask={handleAddInColumn}
            />
          </div>
        )}
      </div>

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        initialTask={null}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          queryClient.invalidateQueries({ queryKey: ["taskStats"] });
        }}
      />
    </div>
  );
}
