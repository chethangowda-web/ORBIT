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
        <div className="inline-block w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mr-3"></div>
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
          className="text-indigo-400 hover:underline text-sm"
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
        <div className="glass-panel rounded-2xl p-6 border border-slate-800/80 space-y-6">
          {/* Header & Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <StatusBadge status={task.status} />
                <PriorityBadge priority={task.priority} />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {task.title}
              </h1>
            </div>

            <div className="flex items-center gap-2.5">
              {task.status !== "DONE" && (
                <button
                  onClick={() => completeMutation.mutate()}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-600/20 transition-all hover:scale-[1.02]"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Mark Complete</span>
                </button>
              )}

              <button
                onClick={() => setIsEditModalOpen(true)}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
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
                className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
              Description
            </h3>
            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
              {task.description || "No description provided."}
            </p>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-800">
            <div>
              <p className="text-[11px] text-slate-500 font-medium">Assignee</p>
              <div className="flex items-center gap-2 mt-1">
                <div className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs text-indigo-400 font-bold uppercase">
                  {task.assignee?.display_name?.charAt(0) || <UserIcon className="w-3 h-3" />}
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
            <div className="pt-4 border-t border-slate-800">
              <p className="text-[11px] text-slate-500 font-medium mb-2">Tags</p>
              <div className="flex flex-wrap gap-1.5">
                {task.tags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-indigo-950/40 text-indigo-300 border border-indigo-500/30"
                  >
                    <Tag className="w-3 h-3 text-indigo-400" />
                    <span>{tag}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Audit History Timeline */}
        <div className="glass-panel rounded-2xl p-6 border border-slate-800/80">
          <div className="flex items-center gap-2 mb-6">
            <Activity className="w-4 h-4 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Audit Trail & Change History
            </h3>
          </div>

          {history.length === 0 ? (
            <p className="text-xs text-slate-500">No recorded audit events yet.</p>
          ) : (
            <div className="relative pl-6 border-l border-slate-800 space-y-6">
              {history.map((log) => (
                <div key={log.id} className="relative group">
                  {/* Dot */}
                  <div className="absolute -left-[31px] top-1 w-3 h-3 rounded-full bg-indigo-500 border-2 border-slate-900 group-hover:scale-125 transition-transform" />

                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-slate-200">
                      {log.action}
                    </span>
                    <span className="text-[11px] text-slate-500">
                      {new Date(log.created_at).toLocaleString()}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400">
                    Source: <span className="text-indigo-300 font-mono text-[11px]">{log.source}</span>
                    {log.user && <span> • by {log.user.display_name}</span>}
                  </p>

                  {log.changes && Object.keys(log.changes).length > 0 && (
                    <div className="mt-2 p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-[11px] font-mono text-slate-300">
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
