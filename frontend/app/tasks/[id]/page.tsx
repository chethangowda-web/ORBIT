"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { Navbar } from "@/components/Navbar";
import { StatusBadge } from "@/components/StatusBadge";
import { PriorityBadge } from "@/components/PriorityBadge";
import { CreateTaskModal } from "@/components/CreateTaskModal";
import {
  ArrowLeft,
  Calendar,
  CheckCircle2,
  Clock,
  Edit3,
  Trash2,
  User as UserIcon,
  Activity,
  Tag,
} from "lucide-react";

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const taskId = params.id as string;

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  // Fetch task
  const { data: task, isLoading } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => api.tasks.get(taskId),
  });

  // Fetch task audit history
  const { data: history = [] } = useQuery({
    queryKey: ["taskHistory", taskId],
    queryFn: () => api.tasks.history(taskId),
  });

  // Mark complete mutation
  const completeMutation = useMutation({
    mutationFn: () => api.tasks.complete(taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", taskId] });
      queryClient.invalidateQueries({ queryKey: ["taskHistory", taskId] });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => api.tasks.delete(taskId),
    onSuccess: () => {
      router.push("/tasks");
    },
  });

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen text-slate-400">
        <div className="inline-block w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-3"></div>
        Loading task details...
      </div>
    );
  }

  if (!task) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-screen text-slate-400 p-6">
        <p className="text-lg font-bold text-slate-200 mb-2">Task not found</p>
        <button
          onClick={() => router.push("/tasks")}
          className="text-blue-400 hover:underline text-sm"
        >
          Return to tasks
        </button>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar title="Task Detail" />

      <div className="p-6 max-w-5xl mx-auto w-full space-y-6">
        {/* Back Button */}
        <div>
          <button
            onClick={() => router.push("/tasks")}
            className="flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to all tasks</span>
          </button>
        </div>

        {/* Main Task Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-5">
          {/* Header & Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-slate-800">
            <div className="space-y-2">
              <div className="flex items-center gap-2.5">
                <StatusBadge status={task.status} />
                <PriorityBadge priority={task.priority} />
              </div>
              <h1 className="text-lg sm:text-xl font-bold text-slate-100 tracking-tight">
                {task.title}
              </h1>
            </div>

            <div className="flex items-center gap-2">
              {task.status !== "DONE" && (
                <button
                  onClick={() => completeMutation.mutate()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Mark Complete</span>
                </button>
              )}

              <button
                onClick={() => setIsEditModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>Edit</span>
              </button>

              <button
                onClick={() => {
                  if (confirm("Are you sure you want to delete this task?")) {
                    deleteMutation.mutate();
                  }
                }}
                className="p-1.5 rounded-md text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
              Description
            </h3>
            <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/80 p-3.5 rounded-md border border-slate-800">
              {task.description || "No description provided."}
            </p>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-800">
            <div>
              <p className="text-[11px] text-slate-500 font-medium">Assignee</p>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-5 h-5 rounded-md bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] text-blue-400 font-bold uppercase">
                  {task.assignee?.display_name?.charAt(0) || <UserIcon className="w-2.5 h-2.5" />}
                </div>
                <span className="text-xs text-slate-200 font-medium">
                  {task.assignee?.display_name || "Unassigned"}
                </span>
              </div>
            </div>

            <div>
              <p className="text-[11px] text-slate-500 font-medium">Due Date</p>
              <div className="flex items-center gap-1.5 mt-1 text-xs text-slate-200 font-medium">
                <Calendar className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {task.due_date
                    ? new Date(task.due_date + "T00:00:00").toLocaleDateString(undefined, {
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })
                    : "No deadline"}
                </span>
              </div>
            </div>

            <div>
              <p className="text-[11px] text-slate-500 font-medium">Created On</p>
              <div className="flex items-center gap-1.5 mt-1 text-xs text-slate-400">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                <span>{new Date(task.created_at).toLocaleDateString()}</span>
              </div>
            </div>

            <div>
              <p className="text-[11px] text-slate-500 font-medium">Creator</p>
              <p className="text-xs text-slate-300 mt-1">
                {task.creator?.display_name || "System"}
              </p>
            </div>
          </div>

          {/* Tags */}
          {task.tags && task.tags.length > 0 && (
            <div className="pt-3.5 border-t border-slate-800">
              <p className="text-[11px] text-slate-500 font-medium mb-1.5">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {task.tags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-blue-950/40 text-blue-300 border border-blue-800/50"
                  >
                    <Tag className="w-3 h-3 text-blue-400" />
                    <span>{tag}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Audit History Timeline */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-2 mb-5">
            <Activity className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              Audit Trail & Change History
            </h3>
          </div>

          {history.length === 0 ? (
            <p className="text-xs text-slate-500">No recorded audit events yet.</p>
          ) : (
            <div className="relative pl-5 border-l border-slate-800 space-y-5">
              {history.map((log) => (
                <div key={log.id} className="relative group">
                  {/* Dot */}
                  <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-slate-900" />

                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-slate-200">
                      {log.action}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400">
                    Source: <span className="text-blue-300 font-mono text-[11px]">{log.source}</span>
                    {log.user && <span> • by {log.user.display_name}</span>}
                  </p>

                  {log.changes && Object.keys(log.changes).length > 0 && (
                    <div className="mt-2 p-2.5 rounded-md bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300">
                      {JSON.stringify(log.changes, null, 2)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      <CreateTaskModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        initialTask={task}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["task", taskId] });
          queryClient.invalidateQueries({ queryKey: ["taskHistory", taskId] });
        }}
      />
    </div>
  );
}
