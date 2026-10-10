"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Task, TaskStatus } from "@/types";
import { Navbar } from "@/components/Navbar";
import { KanbanColumn } from "@/components/KanbanColumn";
import { CreateTaskModal } from "@/components/CreateTaskModal";
import { AskOrbit } from "@/components/AskOrbit";
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
    <div className="flex-1 flex flex-col min-h-screen bg-[#090D13]">
      <Navbar
        title="Dashboard & Kanban"
        onCreateTask={() => {
          setDefaultColumnStatus("TODO");
          setIsModalOpen(true);
        }}
      />

      <div className="p-6 space-y-5 flex-1 flex flex-col">
        {/* Top Summary Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Card 1: Total */}
          <div className="bg-[#111821] border border-[#263241] rounded-md p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Total Active Tasks</p>
              <h3 className="text-xl font-bold font-mono text-slate-100 mt-0.5">
                {stats?.total_tasks ?? tasks.length}
              </h3>
            </div>
            <div className="w-8 h-8 rounded-md bg-[#151F2C] border border-[#263241] flex items-center justify-center text-blue-400">
              <Layers className="w-4 h-4" />
            </div>
          </div>

          {/* Card 2: In Progress */}
          <div className="bg-[#111821] border border-[#263241] rounded-md p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">In Progress</p>
              <h3 className="text-xl font-bold font-mono text-blue-400 mt-0.5">
                {stats?.in_progress_tasks ?? inProgressTasks.length}
              </h3>
            </div>
            <div className="w-8 h-8 rounded-md bg-blue-950/40 border border-blue-800/40 flex items-center justify-center text-blue-400">
              <Clock className="w-4 h-4" />
            </div>
          </div>

          {/* Card 3: Completed */}
          <div className="bg-[#111821] border border-[#263241] rounded-md p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Completed</p>
              <h3 className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
                {stats?.completed_tasks ?? doneTasks.length}
              </h3>
            </div>
            <div className="w-8 h-8 rounded-md bg-emerald-950/40 border border-emerald-800/40 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>

          {/* Card 4: Overdue */}
          <div className="bg-[#111821] border border-[#263241] rounded-md p-3.5 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-medium text-slate-400">Overdue Tasks</p>
              <h3 className="text-xl font-bold font-mono text-rose-400 mt-0.5">
                {stats?.overdue_tasks ?? 0}
              </h3>
            </div>
            <div className="w-8 h-8 rounded-md bg-rose-950/40 border border-rose-800/40 flex items-center justify-center text-rose-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
        </div>

        {/* Kanban Board Container */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-slate-400 text-xs py-12">
            <div className="inline-block w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-2.5"></div>
            <span>Loading board tasks...</span>
          </div>
        ) : (
          <div className="flex-1 flex gap-4 overflow-x-auto pb-4 custom-scrollbar">
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
        defaultStatus={defaultColumnStatus}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          queryClient.invalidateQueries({ queryKey: ["taskStats"] });
        }}
      />

      {/* AI Command Center: Ask ORBIT */}
      <AskOrbit
        onTaskUpdated={() => {
          queryClient.invalidateQueries({ queryKey: ["tasks"] });
          queryClient.invalidateQueries({ queryKey: ["taskStats"] });
        }}
      />
    </div>
  );
}
