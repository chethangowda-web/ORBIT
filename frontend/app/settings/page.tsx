"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { Navbar } from "@/components/Navbar";
import {
  Bot,
  Play,
  Clock,
  CheckCircle2,
  AlertCircle,
  Calendar,
  Server,
  Loader2,
} from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Fetch scheduler status
  const { data: schedulerStatus, refetch } = useQuery({
    queryKey: ["schedulerStatus"],
    queryFn: () => api.admin.status(),
    retry: false,
  });

  // Briefing trigger mutation
  const briefingMutation = useMutation({
    mutationFn: () => api.admin.triggerBriefing(true),
    onSuccess: (data) => {
      setActionMessage(`Daily briefing triggered successfully. Processed: ${data.processed}, Delivered: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`Error triggering briefing: ${err.message}`);
    },
  });

  // Overdue alerts trigger mutation
  const overdueMutation = useMutation({
    mutationFn: () => api.admin.triggerOverdue(true),
    onSuccess: (data) => {
      setActionMessage(`Overdue alerts triggered. Flagged: ${data.tasks_flagged}, Delivered: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`Error triggering overdue alerts: ${err.message}`);
    },
  });

  // Weekly summary trigger mutation
  const weeklyMutation = useMutation({
    mutationFn: () => api.admin.triggerWeekly(true),
    onSuccess: (data) => {
      setActionMessage(`Weekly summary triggered. Delivered: ${data.sent}`);
      refetch();
    },
    onError: (err: any) => {
      setActionMessage(`Error triggering weekly summary: ${err.message}`);
    },
  });

  return (
    <div className="flex-1 flex flex-col min-h-screen">
      <Navbar title="Settings & System Health" />

      <div className="p-6 max-w-5xl mx-auto w-full space-y-5">
        {/* User Profile Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-3 mb-5 pb-4 border-b border-slate-800">
            <div className="w-10 h-10 rounded-md bg-slate-800 border border-slate-700/80 flex items-center justify-center text-blue-400 font-bold text-base uppercase">
              {user?.display_name?.charAt(0) || "U"}
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-100">{user?.display_name}</h2>
              <p className="text-xs text-slate-400">{user?.email}</p>
            </div>
            <span className="ml-auto text-[11px] px-2.5 py-0.5 rounded-md bg-blue-950/60 text-blue-300 border border-blue-800/50 font-semibold uppercase">
              {user?.role}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block mb-1 text-[11px]">Timezone</span>
              <span className="text-slate-200 font-medium">{user?.timezone || "Asia/Kolkata"}</span>
            </div>
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block mb-1 text-[11px]">Google Chat User ID</span>
              <span className="text-slate-200 font-medium font-mono text-[11px]">
                {user?.google_id || "Unlinked (Simulate Mode)"}
              </span>
            </div>
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="text-slate-500 block mb-1 text-[11px]">Account Auth Status</span>
              <span className="text-emerald-400 font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active Authenticated Session
              </span>
            </div>
          </div>
        </div>

        {/* Autonomous Scheduler Controls */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-800">
            <div className="flex items-center gap-2.5">
              <Server className="w-4 h-4 text-blue-400" />
              <div>
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  APScheduler Background Engine
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Autonomous background worker executing periodic briefings and overdue task notifications.
                </p>
              </div>
            </div>

            {schedulerStatus && (
              <span
                className={`text-[11px] px-2.5 py-0.5 rounded-md font-semibold border ${
                  schedulerStatus.running
                    ? "bg-emerald-950/50 text-emerald-400 border-emerald-500/40"
                    : "bg-amber-950/50 text-amber-400 border-amber-500/40"
                }`}
              >
                {schedulerStatus.running ? "Scheduler Running" : "Scheduler Idle"}
              </span>
            )}
          </div>

          {actionMessage && (
            <div className="mb-4 p-3 rounded-md bg-blue-950/40 border border-blue-800/50 text-xs text-blue-200 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <span>{actionMessage}</span>
            </div>
          )}

          {/* Manual Trigger Buttons */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
            <button
              onClick={() => briefingMutation.mutate()}
              disabled={briefingMutation.isPending}
              className="flex items-center justify-center gap-2 p-2.5 rounded-md bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-medium transition-colors"
            >
              {briefingMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400" />
              ) : (
                <Play className="w-3.5 h-3.5 text-blue-400" />
              )}
              <span>Trigger Morning Briefing</span>
            </button>

            <button
              onClick={() => overdueMutation.mutate()}
              disabled={overdueMutation.isPending}
              className="flex items-center justify-center gap-2 p-2.5 rounded-md bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-medium transition-colors"
            >
              {overdueMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
              )}
              <span>Trigger Overdue Alerts</span>
            </button>

            <button
              onClick={() => weeklyMutation.mutate()}
              disabled={weeklyMutation.isPending}
              className="flex items-center justify-center gap-2 p-2.5 rounded-md bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-medium transition-colors"
            >
              {weeklyMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />
              ) : (
                <Calendar className="w-3.5 h-3.5 text-emerald-400" />
              )}
              <span>Trigger Weekly Summary</span>
            </button>
          </div>

          {/* Active Scheduled Jobs List */}
          <div>
            <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2.5">
              Configured Cron Jobs
            </h4>

            {schedulerStatus?.jobs && schedulerStatus.jobs.length > 0 ? (
              <div className="space-y-2">
                {schedulerStatus.jobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-3 rounded-md bg-slate-950/60 border border-slate-800 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-slate-200">{job.name}</span>
                      <span className="text-slate-500 ml-2 font-mono text-[11px]">
                        ID: {job.id}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span>Next Run: {job.next_run_time ? new Date(job.next_run_time).toLocaleString() : "Pending"}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">
                Jobs registered and triggered automatically on API startup.
              </p>
            )}
          </div>
        </div>

        {/* Compact System Operational Status */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="w-4 h-4 text-blue-400" />
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              System Operational Status
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs mt-3">
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="font-semibold text-slate-200 block mb-1 text-[11px]">LangGraph Multi-Agent Router</span>
              <p className="text-slate-400 text-[11px] leading-relaxed">
                Supervisor node with Redis state checkpoints and specialty agents.
              </p>
            </div>
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="font-semibold text-slate-200 block mb-1 text-[11px]">Google Chat Webhooks</span>
              <p className="text-slate-400 text-[11px] leading-relaxed">
                Bi-directional card rendering, HMAC signature verification, and delivery reporting.
              </p>
            </div>
            <div className="p-3 rounded-md bg-slate-950/60 border border-slate-800">
              <span className="font-semibold text-slate-200 block mb-1 text-[11px]">PostgreSQL Database State</span>
              <p className="text-slate-400 text-[11px] leading-relaxed">
                ACID task persistence, user roles, assignment relations, and audit trail.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
